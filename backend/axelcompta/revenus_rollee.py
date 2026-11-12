"""Revenus Rollee → relevés gardés → rapprochés → ventilés (AXE-821).

C'est ce qui rend le chiffre d'affaires et la TVA justes. Composition root
(doc 18), appelé quand Rollee dit que des données sont prêtes (webhook,
AXE-820) et au rattrapage quotidien.

1. Chaque compte relié et connecté du dossier : ses revenus depuis le
   dernier relevé gardé (ou depuis le début de l'exercice). Une période qui
   ne tient pas (brut − frais ≠ versé…) part en quarantaine avec sa raison.
2. Chaque période est gardée une fois (`settlements_plateforme`) ; une
   période déjà ventilée qui change chez Rollee passe « à vérifier ».
3. Une période **terminée** est rapprochée du virement en banque (montant au
   centime près, -3 à +5 jours, nom de la plateforme dans le libellé).
4. Virement trouvé et déjà en recette (706) : une OD de ventilation pose la
   recette brute, la TVA et la commission. Le virement lui-même n'est jamais
   modifié et le 512 ne bouge pas. Au compte d'attente : « à classer », la
   synchro suivante ventilera. Ailleurs, plusieurs candidats, exercice clos :
   « à vérifier », rien n'est écrit.

Rejouer ne crée rien de plus : l'OD a un identifiant tiré du virement, et
un virement déjà ventilé n'est plus candidat.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.engine import Engine

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import EcritureId, TransactionId
from axelcompta.core.pcg import est_compte_banque
from axelcompta.ingestion.ecritures_settlement import (
    SUFFIXE_VENTILATION,
    ecriture_de_ventilation,
)
from axelcompta.ingestion.journal import JournalIngestion
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.providers.base import NormalizedTransaction, PlatformSettlement
from axelcompta.ingestion.providers.rollee import Rejet, lire_revenus
from axelcompta.ingestion.reconciliation import EtatReconciliation, reconcilier
from axelcompta.ingestion.settlements_plateforme import (
    A_RAPPROCHER,
    SettlementsRepository,
    SettlementStocke,
    fusionner,
)
from axelcompta.ingestion.settlements_plateforme_postgres import PostgresSettlements
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Journal, Sens
from axelcompta.ledger.periodes import Periode
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import charger_plateformes
from axelcompta.plateformes_rollee import (
    ServicesRollee,
    branchement_du_dossier,
    client_du_branchement,
)
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.reclassement import projeter

COMPTE_RECETTE = "706"
COMPTE_ATTENTE = "471"
SOURCE = "rollee"
# Les jours déjà gardés sont relus : Rollee complète une période au fil des jours.
RECOUVREMENT = timedelta(days=14)


@dataclass
class DepotsRevenus:
    settlements: SettlementsRepository
    ledger: LedgerService
    journal: JournalIngestion


def depots_postgres(engine: Engine) -> DepotsRevenus:
    return DepotsRevenus(
        PostgresSettlements(engine), PostgresLedgerService(engine), PostgresJournalIngestion(engine)
    )


@dataclass
class Rapprochement:
    """Ce qu'un passage de rapprochement change : relevés et OD à écrire."""

    stockes: list[SettlementStocke] = field(default_factory=list)
    ecritures: list[Ecriture] = field(default_factory=list)


def _banque_debitee(ecriture: Ecriture) -> int:
    return sum(
        ligne.montant.centimes
        for ligne in ecriture.lignes
        if est_compte_banque(ligne.compte) and ligne.sens is Sens.DEBIT
    )


def _contrepartie(ecriture: Ecriture) -> str | None:
    comptes = {
        ligne.compte
        for ligne in ecriture.lignes
        if ligne.sens is Sens.CREDIT and not est_compte_banque(ligne.compte)
    }
    return comptes.pop() if len(comptes) == 1 else None


def _dans(jour: date, periodes: Sequence[Periode]) -> bool:
    return any(debut <= jour <= fin for debut, fin in periodes)


def _virements_libres(
    grand_livre: Sequence[Ecriture], stockes: Sequence[SettlementStocke]
) -> dict[EcritureId, Ecriture]:
    """Les encaissements bancaires pas encore ventilés, tels que les écrans
    les voient (reclassements repliés)."""
    ventiles = {e.reference_piece for e in grand_livre if e.id.endswith(SUFFIXE_VENTILATION)}
    ventiles |= {s.ecriture_id for s in stockes if s.etat == "reconcilie"}
    exclues = annulees(grand_livre)
    return {
        e.id: e
        for e in projeter(grand_livre)
        if e.journal is Journal.BQ
        and e.id not in exclues
        and e.id not in ventiles
        and _banque_debitee(e) > 0
    }


def _issue(
    stocke: SettlementStocke,
    virement: Ecriture,
    tva_recettes_regime: str,
    periodes_closes: Sequence[Periode],
) -> tuple[SettlementStocke, Ecriture | None]:
    """Un relevé et son unique virement : ventilé, à classer ou à vérifier."""
    lie = replace(stocke, ecriture_id=str(virement.id), motif=None)
    if _dans(virement.date, periodes_closes):
        return replace(lie, etat="a_verifier", motif="virement dans un exercice clos"), None
    compte = _contrepartie(virement)
    if compte == COMPTE_ATTENTE:
        return replace(lie, etat="a_classer", motif="virement à classer en recette"), None
    if compte != COMPTE_RECETTE:
        return replace(lie, etat="a_verifier", motif=f"virement classé en {compte}"), None
    try:
        od = ecriture_de_ventilation(
            virement, stocke.settlement, COMPTE_RECETTE, tva_recettes_regime=tva_recettes_regime
        )
    except DomaineError as exc:
        return replace(lie, etat="a_verifier", motif=str(exc)[:200]), None
    return replace(lie, etat="reconcilie"), od


def rapprocher(
    stockes: Sequence[SettlementStocke],
    grand_livre: Sequence[Ecriture],
    dossier: Dossier,
    periodes_closes: Sequence[Periode],
    aujourd_hui: date,
    maintenant: datetime,
) -> Rapprochement:
    """Pur. Seules les périodes terminées sont rapprochées."""
    virements = _virements_libres(grand_livre, stockes)
    transactions = tuple(
        NormalizedTransaction(
            id=TransactionId(str(v.id)),
            dossier_id=v.dossier_id,
            date=v.date,
            montant_cts=_banque_debitee(v),
            libelle=v.libelle,
            source_provider="grand_livre",
            raw_payload={},
        )
        for v in virements.values()
    )
    candidats = [
        s for s in stockes if s.etat in A_RAPPROCHER and s.settlement.period_end < aujourd_hui
    ]
    resultat, pris = Rapprochement(), set[str]()
    for stocke, issue in zip(
        candidats, reconcilier(transactions, tuple(s.settlement for s in candidats)), strict=True
    ):
        if issue.etat is EtatReconciliation.REVUE_MANUELLE:
            suite = replace(stocke, etat="a_verifier", motif="plusieurs virements possibles")
            od = None
        elif issue.transaction is None:
            suite, od = replace(stocke, etat="en_attente_banque", motif=None), None
        elif str(issue.transaction.id) in pris:
            suite = replace(stocke, etat="a_verifier", motif="virement déjà rapproché")
            od = None
        else:
            pris.add(str(issue.transaction.id))
            virement = virements[EcritureId(str(issue.transaction.id))]
            suite, od = _issue(stocke, virement, dossier.tva_recettes_regime, periodes_closes)
        if suite != stocke:
            resultat.stockes.append(replace(suite, maj_le=maintenant))
        if od is not None:
            resultat.ecritures.append(od)
    return resultat


async def _lire(
    services: ServicesRollee, dossier: Dossier, depuis: date, jusqua: date
) -> tuple[list[tuple[str, PlatformSettlement]], list[Rejet]]:
    comptes = [c for c in services.comptes.comptes(dossier.id) if c.connecte]
    if not comptes:
        return [], []
    client = client_du_branchement(services, branchement_du_dossier(services, dossier))
    plateformes = charger_plateformes()
    lus: list[tuple[str, PlatformSettlement]] = []
    rejets: list[Rejet] = []
    try:
        for compte in comptes:
            reponse = await client.revenus(compte.account_id, depuis, jusqua)
            releve = lire_revenus(dossier.id, compte.pour_releve(), reponse, plateformes)
            lus += [(compte.account_id, s) for s in releve.settlements]
            rejets += releve.rejets
    finally:
        await client.aclose()
    return lus, rejets


def _depuis(dossier: Dossier, stockes: Sequence[SettlementStocke]) -> date:
    if not stockes:
        return dossier.exercice_debut
    return max(s.settlement.period_end for s in stockes) - RECOUVREMENT


async def relever_revenus(
    services: ServicesRollee, depots: DepotsRevenus, dossier: Dossier, aujourd_hui: date
) -> str:
    connus = {s.id: s for s in depots.settlements.lister(dossier.id)}
    lus, rejets = await _lire(
        services, dossier, _depuis(dossier, list(connus.values())), aujourd_hui
    )
    for rejet in rejets:
        depots.journal.mettre_en_quarantaine(
            dossier.id, SOURCE, rejet.motif, rejet.account_id, dict(rejet.payload)
        )
    maintenant = datetime.now(UTC)
    nouveaux = []
    for account_id, settlement in lus:
        stocke = fusionner(
            connus.get(f"{account_id}:{settlement.period_start}:{settlement.period_end}"),
            account_id,
            settlement,
            maintenant,
        )
        if stocke is not None:
            nouveaux.append(stocke)
            connus[stocke.id] = stocke
    depots.settlements.enregistrer(nouveaux)
    return _ventiler(depots, dossier, list(connus.values()), aujourd_hui, maintenant, len(rejets))


def _ventiler(
    depots: DepotsRevenus,
    dossier: Dossier,
    stockes: list[SettlementStocke],
    aujourd_hui: date,
    maintenant: datetime,
    nb_rejets: int,
) -> str:
    rapprochement = rapprocher(
        stockes,
        depots.ledger.grand_livre(dossier.id),
        dossier,
        depots.ledger.periodes_closes(dossier.id),
        aujourd_hui,
        maintenant,
    )
    refuses: set[str] = set()
    for od in rapprochement.ecritures:
        try:
            depots.ledger.enregistrer(od)
        except DomaineError as exc:  # une OD refusée laisse son relevé à vérifier
            refuses.add(str(od.reference_piece))
            print(f"{dossier.id} : ventilation refusée ({exc})")
    stockes_finaux = [
        replace(s, etat="a_verifier", motif="ventilation refusée par le grand livre")
        if s.ecriture_id in refuses
        else s
        for s in rapprochement.stockes
    ]
    depots.settlements.enregistrer(stockes_finaux)
    ventiles = len(rapprochement.ecritures) - len(refuses)
    return (
        f"{dossier.id} : {ventiles} versement(s) ventilé(s), "
        f"{sum(1 for s in stockes_finaux if s.etat == 'a_verifier')} à vérifier, "
        f"{nb_rejets} en quarantaine"
    )
