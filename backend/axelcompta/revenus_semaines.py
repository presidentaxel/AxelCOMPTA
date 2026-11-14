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
  un virement a été classé ailleurs qu'en 471 ou 706 par un humain, ou si des
  espèces n'ont pas de compte de l'associé : elle passe « à vérifier ».
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime

from axelcompta.core.errors import DomaineError
from axelcompta.core.pcg import est_compte_banque
from axelcompta.ingestion.ecritures_semaines import (
    SUFFIXE_SOLDE,
    ecriture_frais,
    ecriture_recette,
    ecriture_solde,
    id_recette,
)
from axelcompta.ingestion.providers.rollee import especes_cts, pourboires_cts
from axelcompta.ingestion.semaines_plateforme import (
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
from axelcompta.ledger.periodes import Periode
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.statuts import configuration_de
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
    compte_especes: str | None
    maintenant: datetime


def compte_especes_de(dossier: Dossier) -> str | None:
    """Le compte de l'associé (455, 108 en EI) ; None si la configuration du
    dossier n'est pas lisible."""
    try:
        return configuration_de(dossier).colonne.compte_usage_personnel
    except (DomaineError, ValueError):
        return None


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


def virements_libres(grand_livre: Sequence[Ecriture]) -> dict[str, tuple[Virement, Ecriture]]:
    """Les virements de plateforme pas encore soldés, vus après reclassement."""
    soldes = {e.id for e in grand_livre if e.id.endswith(SUFFIXE_SOLDE)}
    exclus = annulees(grand_livre)
    libres: dict[str, tuple[Virement, Ecriture]] = {}
    for e in projeter(grand_livre):
        if e.journal is not Journal.BQ or e.id in exclus or f"{e.id}{SUFFIXE_SOLDE}" in soldes:
            continue
        montant = _encaisse(e)
        lu = virement(str(e.id), e.date, montant, e.libelle) if montant > 0 else None
        if lu is not None:
            libres[str(e.id)] = (lu, e)
    return libres


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
                contexte.compte_especes,
                semaine.lundi,
                contexte.dossier.tva_recettes_regime,
                pourboires_cts(stocke.settlement),
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
