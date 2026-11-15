"""Comparer ce que Rollee dit gagné et ce que la banque a reçu (AXE-928). Pur.

La banque est la source de vérité de la compta : une semaine n'est écrite
que si ses virements sont trouvés (AXE-924). Rollee, lui, voit tout ce que
le chauffeur a gagné. Mettre les deux côte à côte montre ce qui manque :
un compte bancaire pas encore ajouté, un historique bancaire trop court, un
jour que Rollee ne remonte pas.

Par plateforme et par semaine (lundi → dimanche) :

* **dû** = Σ (gagné net − espèces) des jours Rollee ;
* **versé** = Σ virements de la plateforme attribués à la semaine (POP SVCS,
  instantanés, BOLT FR), soldés ou non ;
* **frais** = 0,99 € par virement instantané ;
* **écart** = dû − versé − frais.

Les années sans banque servent de rapport : CA des courses HT, TVA, revenus
hors course et espèces, calculés comme la recette d'un jour (AXE-926), sans
rien écrire.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from axelcompta.ingestion.providers.base import PlatformSettlement
from axelcompta.ingestion.semaines_plateforme import (
    ATTENTE_VIREMENT,
    FRAIS_INSTANTANE_CTS,
    TOLERANCE_CTS,
    Virement,
    lundi,
)

EtatComparaison = Literal[
    "rapprochee",
    "sans_banque",
    "absente_de_rollee",
    "en_cours",
    "virement_manquant",
    "verse_en_trop",
    "concorde",
]


@dataclass(frozen=True, slots=True)
class JourRollee:
    """Un jour gagné, avec ce qu'il faut pour la TVA et la comparaison."""

    plateforme: str
    jour: date
    gagne_cts: int  # net : brut − commission
    commission_cts: int
    especes_cts: int
    hors_course_cts: int  # pourboires, bonus, autres : sans TVA
    taxable_cts: int  # brut − hors course : la base TTC des courses
    rapproche: bool  # sa semaine est écrite en compta


@dataclass
class Totaux:
    gagne_cts: int = 0
    commission_cts: int = 0
    especes_cts: int = 0
    du_cts: int = 0
    verse_cts: int = 0
    frais_cts: int = 0
    courses_ht_cts: int = 0
    tva_cts: int = 0
    hors_course_cts: int = 0

    @property
    def ecart_cts(self) -> int:
        return self.du_cts - self.verse_cts - self.frais_cts

    def ajouter(self, autre: Totaux) -> None:
        for nom in (
            "gagne_cts",
            "commission_cts",
            "especes_cts",
            "du_cts",
            "verse_cts",
            "frais_cts",
            "courses_ht_cts",
            "tva_cts",
            "hors_course_cts",
        ):
            setattr(self, nom, getattr(self, nom) + getattr(autre, nom))


@dataclass
class SemaineComparee:
    plateforme: str
    lundi: date
    totaux: Totaux
    jours: int
    virements: int
    instantanes: int
    etat: EtatComparaison = "concorde"


@dataclass
class MoisCompare:
    mois: date  # premier jour du mois
    totaux: Totaux = field(default_factory=Totaux)
    semaines: list[SemaineComparee] = field(default_factory=list)


def jour_rollee(
    settlement: PlatformSettlement, especes: int, hors_course: int, rapproche: bool
) -> JourRollee:
    return JourRollee(
        settlement.platform,
        settlement.period_start,
        settlement.net_payout_cts,
        settlement.commission_cts,
        especes,
        hors_course,
        settlement.gross_earnings_cts - hors_course,
        rapproche,
    )


def _tva(taxable_cts: int, taux: Decimal | None) -> tuple[int, int]:
    """(HT, TVA) des courses, au centime comme la recette du jour."""
    if taux is None:
        return taxable_cts, 0
    ht = int((Decimal(taxable_cts) / (1 + taux)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return ht, taxable_cts - ht


def _etat(
    semaine: SemaineComparee, debut_banque: date | None, aujourd_hui: date, toutes_rapprochees: bool
) -> EtatComparaison:
    if semaine.jours and toutes_rapprochees:
        return "rapprochee"
    if not semaine.jours and semaine.totaux.verse_cts:
        # Payée en banque, mais Rollee ne remonte aucun jour : compte de la
        # plateforme pas relié chez Rollee, ou jours manquants.
        return "absente_de_rollee"
    if debut_banque is None or semaine.lundi < lundi(debut_banque):
        return "sans_banque"
    if semaine.lundi + timedelta(days=6) + ATTENTE_VIREMENT >= aujourd_hui:
        return "en_cours"
    ecart = semaine.totaux.ecart_cts
    if ecart > TOLERANCE_CTS:
        return "virement_manquant"
    if ecart < -TOLERANCE_CTS:
        return "verse_en_trop"
    return "concorde"


def comparer(
    jours: Iterable[JourRollee],
    virements: Iterable[Virement],
    debut_banque: date | None,
    aujourd_hui: date,
    taux_tva: Decimal | None,
) -> list[SemaineComparee]:
    """Les semaines de toutes les plateformes, de la plus ancienne à la plus
    récente. Une semaine payée sans aucun jour Rollee apparaît aussi : Rollee
    ne la remonte pas."""
    groupes: dict[tuple[str, date], tuple[list[JourRollee], list[Virement]]] = {}
    for j in jours:
        groupes.setdefault((j.plateforme, lundi(j.jour)), ([], []))[0].append(j)
    for v in virements:
        groupes.setdefault((v.plateforme, v.semaine), ([], []))[1].append(v)
    semaines = []
    for (plateforme, lundi_), (siens, payes) in sorted(
        groupes.items(), key=lambda g: (g[0][1], g[0][0])
    ):
        semaine = _semaine(plateforme, lundi_, siens, payes, taux_tva)
        semaine.etat = _etat(semaine, debut_banque, aujourd_hui, all(j.rapproche for j in siens))
        semaines.append(semaine)
    return semaines


def _semaine(
    plateforme: str,
    lundi_: date,
    siens: Sequence[JourRollee],
    payes: Sequence[Virement],
    taux_tva: Decimal | None,
) -> SemaineComparee:
    totaux = Totaux()
    for j in siens:
        ht, tva = _tva(j.taxable_cts, taux_tva)
        totaux.gagne_cts += j.gagne_cts
        totaux.commission_cts += j.commission_cts
        totaux.especes_cts += j.especes_cts
        totaux.du_cts += j.gagne_cts - j.especes_cts
        totaux.courses_ht_cts += ht
        totaux.tva_cts += tva
        totaux.hors_course_cts += j.hors_course_cts
    instantanes = sum(1 for v in payes if v.nature == "instantane")
    totaux.verse_cts = sum(v.montant_cts for v in payes)
    totaux.frais_cts = FRAIS_INSTANTANE_CTS * instantanes
    return SemaineComparee(plateforme, lundi_, totaux, len(siens), len(payes), instantanes)


def par_mois(semaines: Iterable[SemaineComparee], annee: int) -> list[MoisCompare]:
    """Les mois d'une année. Une semaine est rangée dans le mois de son lundi."""
    mois: dict[date, MoisCompare] = {}
    for semaine in semaines:
        if semaine.lundi.year != annee:
            continue
        cle = semaine.lundi.replace(day=1)
        ligne = mois.setdefault(cle, MoisCompare(cle))
        ligne.semaines.append(semaine)
        ligne.totaux.ajouter(semaine.totaux)
    return [mois[k] for k in sorted(mois)]


def annees(semaines: Iterable[SemaineComparee]) -> list[int]:
    return sorted({s.lundi.year for s in semaines}, reverse=True)
