"""Rapprocher les relevés Rollee d'un dossier semaine par semaine (AXE-924).

Composition root, sans appel : prend les jours gardés, le grand livre et la
configuration du dossier, rend les relevés mis à jour et les OD à écrire.

* Jours : les relevés d'un jour pas encore rapprochés (semaines et mois de
  Rollee ignorés). Dû = gagné net − espèces, pour toutes les plateformes.
* Virements : les encaissements bancaires reconnus comme venant d'une
  plateforme (POP SVCS, Stichting Custodian Uber, BOLT FR), pas encore
  soldés, tels que les écrans les voient (reclassements repliés).
* Semaine soldée : recette de chaque jour, solde par chaque virement, frais.
  Elle n'écrit rien si un jour ou un virement tombe dans un exercice clos, si
  un virement a été classé ailleurs qu'en 471 ou 706 par un humain : elle
  passe « à vérifier ».
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Literal

from axelcompta.core.errors import DomaineError
from axelcompta.core.pcg import est_compte_banque
from axelcompta.ingestion.comparaison_rollee import SemaineComparee, comparer, jour_rollee
from axelcompta.ingestion.ecritures_semaines import (
    SUFFIXE_SOLDE,
    ecriture_frais,
    ecriture_recette,
    ecriture_solde,
    id_recette,
)
from axelcompta.ingestion.ecritures_settlement import TAUX_TVA_RECETTES_PAR_REGIME
from axelcompta.ingestion.providers.base import PlatformSettlement
from axelcompta.ingestion.providers.rollee import especes_cts, hors_course_cts
from axelcompta.ingestion.semaines_plateforme import (
    FRAIS_INSTANTANE_CTS,
    Jour,
    Semaine,
    Virement,
    libelle_ecart,
    lundi,
    rapprocher_plateforme,
    virement,
)
from axelcompta.ingestion.settlements_plateforme import SettlementStocke
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Journal, Sens
from axelcompta.ledger.periodes import Periode, date_de_report
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.reclassement import projeter

A_RAPPROCHER = frozenset({"en_attente_banque", "a_classer", "a_verifier"})
CONTREPARTIES = frozenset({"471", "706"})


@dataclass
class Passage:
    stockes: list[SettlementStocke] = field(default_factory=list)
    ecritures: list[Ecriture] = field(default_factory=list)
    semaines: list[Semaine] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Contexte:
    dossier: Dossier
    periodes_closes: tuple[Periode, ...]
    maintenant: datetime


def _jours(stockes: Sequence[SettlementStocke]) -> dict[str, SettlementStocke]:
    return {
        s.id: s
        for s in stockes
        if s.etat in A_RAPPROCHER and s.settlement.period_start == s.settlement.period_end
    }


def _encaisse(ecriture: Ecriture) -> int:
    return sum(
        x.montant.centimes
        for x in ecriture.lignes
        if est_compte_banque(x.compte) and x.sens is Sens.DEBIT
    )


def _contrepartie(ecriture: Ecriture) -> str | None:
    comptes = {
        x.compte
        for x in ecriture.lignes
        if x.sens is Sens.CREDIT and not est_compte_banque(x.compte)
    }
    return comptes.pop() if len(comptes) == 1 else None


def virements_de_plateforme(
    grand_livre: Sequence[Ecriture],
) -> dict[str, tuple[Virement, Ecriture]]:
    """Tous les virements de plateforme en banque, soldés ou non, vus après
    reclassement ; les virements annulés n'en sont pas."""
    exclus = annulees(grand_livre)
    trouves: dict[str, tuple[Virement, Ecriture]] = {}
    for e in projeter(grand_livre):
        if e.journal is not Journal.BQ or e.id in exclus:
            continue
        montant = _encaisse(e)
        lu = virement(str(e.id), e.date, montant, e.libelle) if montant > 0 else None
        if lu is not None:
            trouves[str(e.id)] = (lu, e)
    return trouves


def virements_libres(grand_livre: Sequence[Ecriture]) -> dict[str, tuple[Virement, Ecriture]]:
    """Les virements de plateforme pas encore soldés."""
    soldes = {e.id for e in grand_livre if e.id.endswith(SUFFIXE_SOLDE)}
    return {
        i: lu
        for i, lu in virements_de_plateforme(grand_livre).items()
        if f"{i}{SUFFIXE_SOLDE}" not in soldes
    }


def comparaison(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    dossier: Dossier,
    aujourd_hui: date,
) -> list[SemaineComparee]:
    """AXE-928 : Rollee et la banque côte à côte, sur tout l'historique Rollee
    gardé. Les jours déliés n'en sont pas."""
    jours = [
        jour_rollee(
            s.settlement,
            _lisible(especes_cts, s),
            _lisible(hors_course_cts, s),
            s.etat == "reconcilie",
        )
        for s in stockes
        if s.etat != "delie" and s.settlement.period_start == s.settlement.period_end
    ]
    virements = [v for v, _e in virements_de_plateforme(grand_livre).values()]
    taux = TAUX_TVA_RECETTES_PAR_REGIME.get(dossier.tva_recettes_regime)
    return comparer(jours, virements, debut_banque(grand_livre), aujourd_hui, taux)


def _lisible(lire: Callable[[PlatformSettlement], int], stocke: SettlementStocke) -> int:
    """Un champ illisible compte pour 0 dans la comparaison (le jour reste
    à vérifier côté rapprochement)."""
    try:
        return lire(stocke.settlement)
    except (DomaineError, ValueError):
        return 0


def _dans(jour: date, periodes: Sequence[Periode]) -> bool:
    return any(debut <= jour <= fin for debut, fin in periodes)


def _ecritures_semaine(
    semaine: Semaine,
    jours: dict[str, SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
    contexte: Contexte,
) -> list[Ecriture]:
    """Les OD d'une semaine soldée. Lève ValueError avec le motif si elle ne
    peut pas s'écrire (rien n'est écrit pour elle)."""
    dates = [jours[j].settlement.period_start for j in semaine.jours]
    dates += [virements[v][1].date for v in semaine.virements]
    if any(_dans(d, contexte.periodes_closes) for d in dates):
        raise ValueError("semaine dans un exercice clos")
    ecritures = []
    for ident in semaine.jours:
        stocke = jours[ident]
        ecritures.append(
            ecriture_recette(
                stocke.id,
                stocke.settlement,
                especes_cts(stocke.settlement),
                semaine.lundi,
                contexte.dossier.tva_recettes_regime,
                hors_course_cts(stocke.settlement),
            )
        )
    for ident in semaine.virements:
        lu, ecriture = virements[ident]
        compte = _contrepartie(ecriture)
        if compte not in CONTREPARTIES:
            raise ValueError(f"virement classé en {compte}")
        ecritures.append(
            ecriture_solde(ecriture, compte, lu.montant_cts, semaine.plateforme, semaine.lundi)
        )
    if semaine.frais_cts:
        le = max(dates)
        ecritures.append(
            ecriture_frais(
                contexte.dossier.id, semaine.plateforme, semaine.lundi, le, semaine.frais_cts
            )
        )
    return ecritures


def _jour(stocke: SettlementStocke) -> Jour:
    s = stocke.settlement
    return Jour(stocke.id, s.platform, s.period_start, s.net_payout_cts - especes_cts(s))


def _suite(
    stocke: SettlementStocke, semaine: Semaine, motif: str | None, contexte: Contexte
) -> SettlementStocke:
    if semaine.etat == "solde" and motif is None:
        return replace(
            stocke,
            etat="reconcilie",
            motif=None,
            ecriture_id=str(id_recette(stocke.id)),
            maj_le=contexte.maintenant,
        )
    if semaine.etat == "en_attente" and motif is None:
        return replace(stocke, etat="en_attente_banque", motif=None, maj_le=contexte.maintenant)
    texte = motif or f"semaine du {semaine.lundi:%d/%m} : {libelle_ecart(semaine)}"
    return replace(stocke, etat="a_verifier", motif=texte[:200], maj_le=contexte.maintenant)


def debut_banque(grand_livre: Sequence[Ecriture]) -> date | None:
    """La première opération bancaire du dossier. Avant elle, aucun virement
    ne peut être trouvé : les jours Rollee de ces semaines restent en attente
    (pas « à vérifier »), sinon le chauffeur verrait des mois de jours à
    traiter pour un historique bancaire qui n'existe pas (AXE-833)."""
    dates = [e.date for e in grand_livre if e.journal is Journal.BQ]
    return min(dates) if dates else None


def rapprocher_semaines(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    contexte: Contexte,
    aujourd_hui: date,
) -> Passage:
    debut = debut_banque(grand_livre)
    jours = {
        i: s
        for i, s in _jours(stockes).items()
        if debut is not None and lundi(s.settlement.period_start) >= lundi(debut)
    }
    virements = virements_libres(grand_livre)
    passage = Passage()
    for plateforme in sorted({s.settlement.platform for s in jours.values()}):
        siens = [_jour(s) for s in jours.values() if s.settlement.platform == plateforme]
        payes = [v for v, _e in virements.values() if v.plateforme == plateforme]
        for semaine in rapprocher_plateforme(plateforme, siens, payes, aujourd_hui):
            motif: str | None = None
            if semaine.etat == "solde":
                try:
                    passage.ecritures += _ecritures_semaine(semaine, jours, virements, contexte)
                except ValueError as exc:
                    motif = f"semaine du {semaine.lundi:%d/%m} : {exc}"
            passage.semaines.append(semaine)
            passage.stockes += [_suite(jours[j], semaine, motif, contexte) for j in semaine.jours]
    return passage


# AXE-912 : ce que l'expert-comptable décide pour une semaine qui ne retombe
# pas juste seule.
Decision = Literal["ecrire", "ecarter"]


class RienATrancher(DomaineError):
    """Aucun jour ni virement de cette semaine n'attend une décision."""


def trancher_semaine(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    contexte: Contexte,
    semaine: tuple[str, date],
    decision: Decision,
    motif: str,
) -> Passage:
    """AXE-912 : sortir une semaine (plateforme, lundi) de « à vérifier ».

    * `ecrire` : la recette de chaque jour, le solde de chaque virement de
      la semaine (sauf ceux qu'un humain a classés ailleurs qu'en 471 ou
      706 : leur classement est gardé) et les frais d'instantanés. L'écart
      reste sur la créance de la plateforme (467x), visible au bilan. Une
      date dans un exercice clos passe au premier jour de l'exercice ouvert.
    * `ecarter` : les jours sortent de la comptabilité (`delie`), rien n'est
      écrit. Pour des jours qui ne sont pas des recettes de la société.

    Rejouer n'écrit rien de plus : les identifiants dérivent du jour, du
    virement ou de la semaine."""
    plateforme, lundi_ = semaine
    jours, virements = _de_la_semaine(stockes, grand_livre, plateforme, lundi_)
    if not jours and (decision == "ecarter" or not virements):
        raise RienATrancher(
            f"Rien à trancher pour {plateforme.capitalize()}, semaine du {lundi_:%d/%m/%Y}."
        )
    trace = motif.strip()[:150]
    if decision == "ecarter":
        return Passage(
            stockes=[
                replace(
                    s,
                    etat="delie",
                    motif=f"écarté par l'expert : {trace}"[:200],
                    maj_le=contexte.maintenant,
                )
                for s in jours
            ]
        )
    ecritures = _ecritures_tranchees(plateforme, lundi_, jours, virements, contexte)
    return Passage(
        stockes=[
            replace(
                s,
                etat="reconcilie",
                motif=f"écrit par l'expert : {trace}"[:200],
                ecriture_id=str(id_recette(s.id)),
                maj_le=contexte.maintenant,
            )
            for s in jours
        ],
        ecritures=ecritures,
    )


def _de_la_semaine(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    plateforme: str,
    lundi_: date,
) -> tuple[list[SettlementStocke], dict[str, tuple[Virement, Ecriture]]]:
    """Les jours en attente et les virements libres d'une semaine."""
    jours = [
        s
        for s in _jours(stockes).values()
        if s.settlement.platform == plateforme and lundi(s.settlement.period_start) == lundi_
    ]
    virements = {
        i: (lu, e)
        for i, (lu, e) in virements_libres(grand_livre).items()
        if lu.plateforme == plateforme and lu.semaine == lundi_
    }
    return jours, virements


def _ecritures_tranchees(
    plateforme: str,
    lundi_: date,
    jours: Sequence[SettlementStocke],
    virements: dict[str, tuple[Virement, Ecriture]],
    contexte: Contexte,
) -> list[Ecriture]:
    dossier = contexte.dossier
    ecritures = [
        ecriture_recette(
            s.id,
            s.settlement,
            especes_cts(s.settlement),
            lundi_,
            dossier.tva_recettes_regime,
            hors_course_cts(s.settlement),
        )
        for s in jours
    ]
    instantanes = 0
    for lu, ecriture in virements.values():
        compte = _contrepartie(ecriture)
        if compte not in CONTREPARTIES:
            continue  # classé ailleurs par un humain : on n'y touche pas
        ecritures.append(ecriture_solde(ecriture, compte, lu.montant_cts, plateforme, lundi_))
        instantanes += lu.nature == "instantane"
    if instantanes:
        dates = [s.settlement.period_start for s in jours] + [
            lu.le for lu, _e in virements.values()
        ]
        ecritures.append(
            ecriture_frais(
                dossier.id, plateforme, lundi_, max(dates), FRAIS_INSTANTANE_CTS * instantanes
            )
        )
    return [
        replace(
            e,
            date=date_de_report(e.date, contexte.periodes_closes, dossier.exercice_debut),
        )
        for e in ecritures
    ]
