"""Synchronisation Digifactory de tout un portefeuille (doc 16 §9).

Composition root comme `demo_api.py` et `demo_seed.py` (doc 18). Pas de
planificateur : tant que la file de jobs (ADR-002) n'existe pas, on lance ça à
la main ou depuis un cron. Chaque dossier est indépendant : l'échec de l'un
n'empêche pas les autres, et le code de sortie vaut 1 si l'un a échoué.

Usage, depuis backend/ (DATABASE_URL, DIGIFACTORY_BASE_URL et
DIGIFACTORY_TOKEN définis, migrations appliquées) :

    python -m axelcompta.synchro_digifactory --tenant <tenant_id>
    python -m axelcompta.synchro_digifactory --dossier <dossier_id>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any, Protocol

from sqlalchemy.engine import Engine

from axelcompta.categorize.ml_fallback import charger_calibration
from axelcompta.categorize.modele_requis import SynchroSansModele, modele_pour_synchro
from axelcompta.categorize.pipeline import CategorizationPipeline, SansClassement
from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaireRepository,
    comptes_releves,
    relever_comptes,
)
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.consentement import (
    ConsentementRepository,
    classer,
    expiration_la_plus_proche,
    relever_sante,
)
from axelcompta.ingestion.consentement_postgres import PostgresConsentementRepository
from axelcompta.ingestion.journal import JournalIngestion
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.providers.digifactory import DigifactoryHttpClient, DigifactoryProvider
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_regles,
)
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.tags import etat_du_portefeuille, exclus, retenus
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.workflow.propositions import PropositionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.synchro import RapportSynchro, SourceTransactions, synchroniser_dossier

SOURCE = "digifactory"


class ClientComptes(Protocol):
    """Ce que le relevé des consentements lit chez Digifactory."""

    async def accounts(self, contact_nr: str | int) -> dict[str, Any] | list[Any]: ...


@dataclass(frozen=True, slots=True)
class ResultatDossier:
    dossier_id: DossierId
    rapport: RapportSynchro | None = None
    ignore: str | None = None  # raison, si le dossier n'a pas été traité
    erreur: str | None = None
    consentement: str | None = None
    sante: str | None = None


async def synchroniser_dossiers(
    dossiers: tuple[Dossier, ...],
    source: SourceTransactions,
    journal: JournalIngestion,
    ledger: LedgerService,
    propositions: PropositionRepository,
    pipeline: CategorizationPipeline,
    comptes: dict[str, str],
    comptes_bancaires: CompteBancaireRepository | None = None,
    sans_classement: frozenset[DossierId] = frozenset(),
) -> list[ResultatDossier]:
    """`sans_classement` : dossiers dont les opérations entrent sans
    classement automatique (tag exclu du traitement, AXE-829)."""
    resultats: list[ResultatDossier] = []
    for dossier in dossiers:
        if dossier.contact_nr is None:
            resultats.append(ResultatDossier(dossier.id, ignore="pas de contact Digifactory"))
            continue
        etages = SansClassement() if dossier.id in sans_classement else pipeline
        try:
            rapport = await synchroniser_dossier(
                dossier,
                source,
                SOURCE,
                journal,
                ledger,
                propositions,
                etages,
                comptes,
                comptes_bancaires,
            )
        except Exception as exc:  # noqa: BLE001 — un dossier en échec ne bloque pas les autres
            resultats.append(ResultatDossier(dossier.id, erreur=f"{type(exc).__name__}: {exc}"))
        else:
            resultats.append(ResultatDossier(dossier.id, rapport=rapport))
    return resultats


def _afficher(resultat: ResultatDossier) -> None:
    if resultat.erreur:
        print(f"{resultat.dossier_id} : ECHEC {resultat.erreur}")
    elif resultat.ignore:
        print(f"{resultat.dossier_id} : ignoré ({resultat.ignore})")
    elif resultat.rapport:
        r = resultat.rapport
        print(
            f"{resultat.dossier_id} : {r.nouvelles} nouvelles ({r.a_trancher} à trancher), "
            f"{r.deja_connues} déjà connues, {r.modifiees_signalees} modifiées et "
            f"{r.supprimees_signalees} supprimées signalées, {r.rejets} rejetées"
            + (f", consentement {resultat.consentement}" if resultat.consentement else "")
            + (f", connexion {resultat.sante}" if resultat.sante else "")
        )


async def _relever_consentements(
    client: ClientComptes,
    dossiers: tuple[Dossier, ...],
    resultats: list[ResultatDossier],
    depots: tuple[ConsentementRepository, CompteBancaireRepository],
    aujourd_hui: date,
) -> list[ResultatDossier]:
    """Après la synchro des transactions : lit `/accounts`, mémorise le
    statut du consentement, et le nom et le solde de chaque compte bancaire
    (AXE-832). Un échec ici n'annule pas les écritures déjà posées."""
    depot, comptes_bancaires = depots
    releves: list[ResultatDossier] = []
    for dossier, resultat in zip(dossiers, resultats, strict=True):
        if dossier.contact_nr is None:
            payload: dict[str, object] | list[object] = []
        else:
            try:
                payload = await client.accounts(dossier.contact_nr)
            except Exception as exc:  # noqa: BLE001 — le relevé ne doit pas effacer la synchro
                releves.append(resultat)
                print(f"{dossier.id} : consentement non relu ({type(exc).__name__})")
                continue
        expire_le = expiration_la_plus_proche(payload)
        statut = classer(expire_le, aujourd_hui)
        sante = relever_sante(payload)
        maintenant = datetime.now(UTC)
        depot.enregistrer(dossier.id, expire_le, statut, maintenant, sante)
        relever_comptes(comptes_bancaires, dossier.id, comptes_releves(payload), maintenant)
        releves.append(replace(resultat, consentement=statut.value, sante=sante.statut.value))
    return releves


def synchroniser_portefeuille(
    engine: Engine,
    dossiers: tuple[Dossier, ...],
    sans_classement: frozenset[DossierId] = frozenset(),
) -> list[ResultatDossier]:
    """Synchro + relevé des consentements, pour un lot de dossiers. Point
    d'entrée partagé par la ligne de commande et les tâches planifiées
    (`axelcompta.taches`)."""
    try:
        modele = modele_pour_synchro()
    except SynchroSansModele as refus:
        # AXE-825 : aucun dossier rempli de 471 en silence.
        return [ResultatDossier(d.id, erreur=str(refus)) for d in dossiers]
    pipeline = RulesAndMlPipeline(
        regles=charger_regles(),
        modele=modele,
        calibration=charger_calibration() if modele is not None else None,
        categories_banque=charger_categories_banque(),
    )

    async def lancer() -> list[ResultatDossier]:
        client = DigifactoryHttpClient.depuis_env()
        try:
            sante = await DigifactoryProvider(client_reel=client).health()
            if not sante.ok:
                print(f"Digifactory indisponible : {sante.message}", file=sys.stderr)
                return [ResultatDossier(d.id, erreur=sante.message) for d in dossiers]
            comptes_bancaires = PostgresCompteBancaireRepository(engine)
            resultats = await synchroniser_dossiers(
                dossiers,
                DigifactoryProvider(client_reel=client),
                PostgresJournalIngestion(engine),
                PostgresLedgerService(engine),
                PostgresPropositionRepository(engine),
                pipeline,
                charger_compte_par_categorie(),
                comptes_bancaires,
                sans_classement,
            )
            return await _relever_consentements(
                client,
                dossiers,
                resultats,
                (PostgresConsentementRepository(engine), comptes_bancaires),
                date.today(),
            )
        finally:
            await client.aclose()

    return asyncio.run(lancer())


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    groupe = parseur.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--tenant")
    groupe.add_argument("--dossier")
    args = parseur.parse_args()

    engine = engine_depuis_env()
    depot = PostgresDossierRepository(engine)
    if args.dossier:
        dossier = depot.obtenir(DossierId(args.dossier))
        if dossier is None:
            print(f"Dossier inconnu : {args.dossier}", file=sys.stderr)
            return 1
        dossiers: tuple[Dossier, ...] = (dossier,)
        sans_classement: frozenset[DossierId] = frozenset()
    else:
        # Un dossier demandé nommément passe toujours ; un portefeuille suit
        # ses tags (AXE-829).
        tenant_id = TenantId(args.tenant)
        etat = etat_du_portefeuille(PostgresTagsRepository(engine), tenant_id)
        tous = depot.lister_par_tenant(tenant_id)
        dossiers = retenus(tous, etat, "synchro")
        sans_classement = exclus(tous, etat, "categorisation")

    resultats = synchroniser_portefeuille(engine, dossiers, sans_classement)
    for resultat in resultats:
        _afficher(resultat)
    return 1 if any(r.erreur for r in resultats) else 0


if __name__ == "__main__":
    sys.exit(main())
