"""Exécuter AXE-833 : relire les relevés d'une fiche, vérifier, écrire.

Composition root (doc 18) : `releves_en_compta.py` dit quoi écrire ; ici,
on relit les fichiers et on passe les opérations par la synchro ordinaire
(`workflow.synchro.synchroniser_dossier`, source `releve`). Lancé par le
worker (job `releves_fiche`), qui a le rôle propriétaire.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.engine import Engine

from axelcompta.categorize.ml_fallback import charger_calibration
from axelcompta.categorize.modele_requis import modele_pour_synchro
from axelcompta.categorize.pipeline import CategorizationPipeline
from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_bancaires import CompteBancaireRepository
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.journal import JournalIngestion
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.providers.base import LotTransactions, NormalizedTransaction
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_regles,
)
from axelcompta.releves_en_compta import (
    SOURCE_RELEVE,
    avec_mouvements,
    lire_releves,
    planifier,
    transactions,
)
from axelcompta.stockage_documents import depot_documents
from axelcompta.tenants.fiches_import_depot import FichesImportRepository
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.workflow.propositions import PropositionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.synchro import synchroniser_dossier


@dataclass(frozen=True, slots=True)
class _SourceFixe:
    """Un seul lot, déjà prêt : les opérations des relevés."""

    lot: tuple[NormalizedTransaction, ...]

    async def lire_lot(self, dossier: Dossier, depuis_maj: datetime | None) -> LotTransactions:
        return LotTransactions(transactions=self.lot)


@dataclass(frozen=True, slots=True)
class Depots:
    fiches: FichesImportRepository
    dossiers: DossierRepository
    comptes: CompteBancaireRepository
    ledger: LedgerService
    journal: JournalIngestion
    propositions: PropositionRepository


def ecrire_releves(
    depots: Depots,
    tenant_id: TenantId,
    fiche_id: str,
    pipeline: CategorizationPipeline,
    comptes_par_categorie: dict[str, str],
    aujourd_hui: date,
) -> str:
    """Le résumé pour l'écran : opérations écrites par compte, et la raison
    de chaque compte non écrit."""
    instantane = depots.fiches.instantane(tenant_id, fiche_id)
    fiche = instantane.fiche
    dossier = depots.dossiers.obtenir(DossierId(fiche.dossier_id)) if fiche.dossier_id else None
    if dossier is None:
        return "La fiche n'a pas encore de dossier : rien d'écrit."

    def contenu(document_id: str) -> bytes:
        return depots.fiches.contenu(tenant_id, document_id)[1]

    qif = [d for d in instantane.documents if (d.donnees or {}).get("type") == "qif"]
    lus = dict(lire_releves([d.id for d in qif], contenu))
    documents = [avec_mouvements(d, lus[d.id]) if d.id in lus else d for d in instantane.documents]
    comptes = depots.comptes.lister(dossier.id)
    plan = planifier(
        fiche,
        documents,
        comptes,
        depots.ledger.grand_livre(dossier.id),
        dossier.exercice_debut,
        aujourd_hui,
    )
    morceaux = list(plan.refus)
    for a_ecrire in plan.comptes:
        lot = transactions(
            dossier.id, a_ecrire, [(i, lus[i]) for i in a_ecrire.documents if i in lus]
        )
        rapport = asyncio.run(
            synchroniser_dossier(
                dossier,
                _SourceFixe(lot),
                SOURCE_RELEVE,
                depots.journal,
                depots.ledger,
                depots.propositions,
                pipeline,
                comptes_par_categorie,
                depots.comptes,
            )
        )
        nom = a_ecrire.compte.nom or a_ecrire.compte.compte_comptable
        morceaux.append(
            f"{nom} : {rapport.nouvelles} opération(s) écrite(s) du "
            f"{a_ecrire.depuis:%d/%m/%Y} au {a_ecrire.avant:%d/%m/%Y} exclu"
            f" ({rapport.a_trancher} à trancher, {rapport.deja_connues} déjà connue(s))"
        )
    return " · ".join(morceaux) or "Aucun relevé rattaché à un compte Digifactory."


def ecrire_releves_postgres(engine: Engine, tenant_id: TenantId, fiche_id: str) -> str:
    """Le job `releves_fiche` du worker. Sans modèle de catégorisation, la
    synchro refuse d'écrire (AXE-825) : on s'arrête aussi."""
    modele = modele_pour_synchro()
    pipeline = RulesAndMlPipeline(
        regles=charger_regles(),
        modele=modele,
        calibration=charger_calibration() if modele is not None else None,
        categories_banque=charger_categories_banque(),
    )
    depots = Depots(
        PostgresFichesImport(engine, depot_documents()),
        PostgresDossierRepository(engine),
        PostgresCompteBancaireRepository(engine),
        PostgresLedgerService(engine),
        PostgresJournalIngestion(engine),
        PostgresPropositionRepository(engine),
    )
    return ecrire_releves(
        depots, tenant_id, fiche_id, pipeline, charger_compte_par_categorie(), date.today()
    )
