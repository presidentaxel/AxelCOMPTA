"""Rapprocher les revenus d'une plateforme semaine par semaine (AXE-924). Pur.

Ce que disent les vraies données (pilote du 14/11, vérifié au centime) :

* Rollee donne le gagné **par jour** (`net_amount` = brut − commission) ;
  ses semaines et ses mois se chevauchent avec les jours et sont ignorés.
* Uber verse chaque lundi, via **POP SVCS**, le solde de la semaine
  précédente ; le libellé porte la période (« 20261102 - 20261108 »).
* En cours de semaine, le chauffeur peut retirer une partie en **virement
  instantané** (« Stichting Custodian Uber Payments ») : 0,99 € de frais
  chacun, mais pas toujours.
* Bolt verse chaque lundi la semaine précédente (« … BOLT FR »).
* Les courses payées en **espèces** (`cash_earnings`) ne passent pas par la
  banque : elles ne sont pas dues par la plateforme.

Pour chaque plateforme, semaine (lundi → dimanche) après semaine :
dû = Σ (gagné net − espèces) des jours ; payé = Σ virements attribués ;
écart = dû − payé (+ report des semaines non soldées).

* écart nul, ou égal à k × 0,99 € avec k ≤ nombre de virements instantanés :
  **soldé**, les frais vont en charge ;
* semaine finie depuis moins de `ATTENTE_VIREMENT` : **en attente** du
  virement ;
* sinon : **à vérifier**, avec l'écart chiffré. Si la semaine suivante ne
  retombe pas juste seule mais juste **avec** celle-ci (un retrait
  instantané qui emporte le reste de la semaine d'avant), les deux sont
  soldées ensemble. Le report ne dure qu'une semaine : un écart jamais
  expliqué ne bloque pas les suivantes.

Rien n'est inventé : un groupe qui ne retombe pas juste n'écrit rien.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

FRAIS_INSTANTANE_CTS = 99
TOLERANCE_CTS = 1
# Le POP SVCS d'une semaine arrive le lundi suivant ; on lui laisse une semaine.
ATTENTE_VIREMENT = timedelta(days=8)

EtatSemaine = Literal["solde", "en_attente", "a_verifier"]
Nature = Literal["hebdomadaire", "instantane"]

_PERIODE_POP = re.compile(r"(\d{8})\s*-\s*(\d{8})")


@dataclass(frozen=True, slots=True)
class Jour:
    """Un jour gagné sur une plateforme, lu chez Rollee."""

    id: str
    plateforme: str
    jour: date
    du_cts: int  # gagné net − espèces : ce que la plateforme doit verser


@dataclass(frozen=True, slots=True)
class Virement:
    """Un encaissement bancaire reconnu comme venant d'une plateforme."""

    id: str
    plateforme: str
    le: date
    montant_cts: int
    nature: Nature
    semaine: date  # le lundi de la semaine qu'il paie


@dataclass(frozen=True, slots=True)
class Semaine:
    plateforme: str
    lundi: date
    etat: EtatSemaine
    du_cts: int
    paye_cts: int
    frais_cts: int = 0
    ecart_cts: int = 0  # reste dû après frais (avec le report) ; 0 si soldée
    jours: tuple[str, ...] = ()
    virements: tuple[str, ...] = ()

    @property
    def dimanche(self) -> date:
        return self.lundi + timedelta(days=6)


def lundi(jour: date) -> date:
    return jour - timedelta(days=jour.weekday())


def plateforme_du_libelle(libelle: str) -> str | None:
    """« POP SVCS » et « Stichting Custodian Uber Payments » : Uber ;
    « … BOLT FR » : Bolt. Le reste n'est pas un versement de plateforme."""
    texte = libelle.upper()
    if "POP SVCS" in texte or re.search(r"\bUBER\b", texte):
        return "uber"
    if re.search(r"\bBOLT\b", texte):
        return "bolt"
    return None


def _periode_pop(libelle: str) -> date | None:
    trouve = _PERIODE_POP.search(libelle)
    if trouve is None:
        return None
    try:
        debut = date(int(trouve[1][:4]), int(trouve[1][4:6]), int(trouve[1][6:]))
    except ValueError:
        return None
    return lundi(debut)


def virement(identifiant: str, jour: date, montant_cts: int, libelle: str) -> Virement | None:
    """Reconnaît un virement de plateforme et la semaine qu'il paie."""
    plateforme = plateforme_du_libelle(libelle)
    if plateforme is None:
        return None
    texte = libelle.upper()
    if plateforme == "uber" and "POP SVCS" not in texte:
        # Retrait instantané : il paie la semaine en cours.
        return Virement(identifiant, plateforme, jour, montant_cts, "instantane", lundi(jour))
    semaine = _periode_pop(libelle) if "POP SVCS" in texte else None
    payee = semaine or lundi(jour - timedelta(days=7))
    return Virement(identifiant, plateforme, jour, montant_cts, "hebdomadaire", payee)


def _frais(ecart: int, instantanes: int) -> int | None:
    """Les frais qui expliquent l'écart, ou None : 0, ou k × 0,99 € avec
    k ≤ nombre de retraits instantanés, à 1 centime près."""
    for k in range(instantanes + 1):
        if abs(ecart - k * FRAIS_INSTANTANE_CTS) <= TOLERANCE_CTS:
            return ecart if k else 0
    return None


@dataclass(frozen=True, slots=True)
class _Part:
    """Une semaine finie, avant de trancher."""

    lundi: date
    du: int
    paye: int
    instantanes: int
    jours: tuple[str, ...]
    virements: tuple[str, ...]


def _part(lundi_: date, siens: Sequence[Jour], payes: Sequence[Virement]) -> _Part:
    return _Part(
        lundi_,
        sum(j.du_cts for j in siens),
        sum(v.montant_cts for v in payes),
        sum(1 for v in payes if v.nature == "instantane"),
        tuple(j.id for j in siens),
        tuple(v.id for v in payes),
    )


def _soldee(part: _Part, plateforme: str, frais: int) -> Semaine:
    return Semaine(
        plateforme, part.lundi, "solde", part.du, part.paye, frais, 0, part.jours, part.virements
    )


def _ouverte(part: _Part, plateforme: str, etat: EtatSemaine) -> Semaine:
    return Semaine(
        plateforme,
        part.lundi,
        etat,
        part.du,
        part.paye,
        0,
        part.du - part.paye,
        part.jours,
        part.virements,
    )


def _avec_la_precedente(
    precedente: _Part | None, part: _Part, plateforme: str
) -> list[Semaine] | None:
    """Un retrait qui emporte le reste de la semaine d'avant : les deux
    semaines, cumulées, retombent juste. Les frais vont sur la seconde."""
    if precedente is None:
        return None
    frais = _frais(
        precedente.du + part.du - precedente.paye - part.paye,
        precedente.instantanes + part.instantanes,
    )
    if frais is None:
        return None
    return [_soldee(precedente, plateforme, 0), _soldee(part, plateforme, frais)]


def rapprocher_plateforme(
    plateforme: str, jours: Sequence[Jour], virements: Sequence[Virement], aujourd_hui: date
) -> list[Semaine]:
    """Les semaines finies d'une plateforme, de la plus ancienne à la plus
    récente. Une semaine qui ne retombe pas juste seule peut l'être avec la
    précédente (report d'une seule semaine) ; sinon elle reste ouverte."""
    par_lundi: dict[date, tuple[list[Jour], list[Virement]]] = {}
    for j in jours:
        par_lundi.setdefault(lundi(j.jour), ([], []))[0].append(j)
    for v in virements:
        par_lundi.setdefault(v.semaine, ([], []))[1].append(v)
    resultat: dict[date, Semaine] = {}
    precedente: _Part | None = None
    for lundi_ in sorted(par_lundi):
        if lundi_ + timedelta(days=6) >= aujourd_hui:
            break  # semaine pas finie : on ne tranche pas
        part = _part(lundi_, *par_lundi[lundi_])
        frais = _frais(part.du - part.paye, part.instantanes)
        if frais is not None:
            resultat[lundi_], precedente = _soldee(part, plateforme, frais), None
            continue
        cumul = _avec_la_precedente(precedente, part, plateforme)
        if cumul is not None:
            for semaine in cumul:
                resultat[semaine.lundi] = semaine
            precedente = None
            continue
        recente = lundi_ + timedelta(days=6) + ATTENTE_VIREMENT >= aujourd_hui
        resultat[lundi_] = _ouverte(part, plateforme, "en_attente" if recente else "a_verifier")
        precedente = part
    return [resultat[k] for k in sorted(resultat)]


def libelle_ecart(semaine: Semaine) -> str:
    """« 12,34 € encore dus par Uber » / « 12,34 € versés en trop par Uber »."""
    montant = f"{abs(semaine.ecart_cts) / 100:.2f}".replace(".", ",")
    if semaine.ecart_cts >= 0:
        return f"{montant} € encore dus par {semaine.plateforme.capitalize()}"
    return f"{montant} € versés en trop par {semaine.plateforme.capitalize()}"
