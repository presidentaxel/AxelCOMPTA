"""PostgresJournalIngestion contre un vrai Postgres, puis une synchro
complète (Digifactory sur payload injecté) qui traverse ledger, propositions
et journal réels."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.db import metadata
from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ingestion.providers.digifactory import DigifactoryProvider
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.notifications import NotificationEnvoyee
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.synchro import synchroniser_dossier

pytestmark = pytest.mark.integration

DOSSIER_ID = DossierId("d-sync")
PAYLOAD = {
    "acc": [
        {
            "id": "t1",
            "provider_description": "CARTE TOTAL STATION",
            "amount": -60.0,
            "date": "2026-03-01",
            "updated_at": "2026-03-01 10:00:00",
            "deleted": False,
            "future": False,
        },
        {"provider_description": "SANS ID", "amount": 1.0},
    ]
}


def _preparer(engine: Engine) -> Dossier:
    metadata.create_all(engine)
    dossiers = PostgresDossierRepository(engine)
    dossiers.enregistrer_tenant(Tenant(id=TenantId("t"), nom="T"))
    dossier = Dossier(
        id=DOSSIER_ID,
        tenant_id=TenantId("t"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="Sync",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 1),
        contact_nr="42",
    )
    dossiers.enregistrer(dossier)
    return dossier


def _synchroniser(engine: Engine, dossier: Dossier):  # type: ignore[no-untyped-def]
    return asyncio.run(
        synchroniser_dossier(
            dossier,
            DigifactoryProvider(payload=PAYLOAD),
            "digifactory",
            PostgresJournalIngestion(engine),
            PostgresLedgerService(engine),
            PostgresPropositionRepository(engine),
            RulesAndMlPipeline(regles=charger_regles(), modele=None),
            charger_compte_par_categorie(),
        )
    )


def test_synchro_de_bout_en_bout_sur_postgres_est_idempotente(engine: Engine) -> None:
    dossier = _preparer(engine)

    premiere = _synchroniser(engine, dossier)
    seconde = _synchroniser(engine, dossier)

    assert (premiere.nouvelles, premiere.rejets) == (1, 1)
    assert (seconde.nouvelles, seconde.deja_connues) == (0, 1)
    assert len(PostgresLedgerService(engine).grand_livre(DOSSIER_ID)) == 1
    journal = PostgresJournalIngestion(engine)
    assert journal.curseur(DOSSIER_ID, "digifactory") == datetime(2026, 3, 1, 10, 0, 0)
    (rejet,) = journal.lister_quarantaine(DOSSIER_ID)
    assert rejet.motif.startswith("ligne_illisible")
    with engine.connect() as connexion:
        assert connexion.execute(text("SELECT count(*) FROM ingestion_brut")).scalar() == 2


def test_le_curseur_ne_recule_jamais(engine: Engine) -> None:
    _preparer(engine)
    journal = PostgresJournalIngestion(engine)

    journal.avancer_curseur(DOSSIER_ID, "digifactory", datetime(2026, 5, 1))
    journal.avancer_curseur(DOSSIER_ID, "digifactory", datetime(2026, 4, 1))

    assert journal.curseur(DOSSIER_ID, "digifactory") == datetime(2026, 5, 1)
    assert journal.curseur(DossierId("autre"), "digifactory") is None


def test_notifications_persistees_avec_les_ecritures_signalees(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d-notif")
    depot = PostgresNotificationRepository(engine)
    assert depot.derniere(DossierId("d-notif"), "a_trancher") is None

    depot.enregistrer(
        NotificationEnvoyee(
            id="n1",
            dossier_id=DossierId("d-notif"),
            type="a_trancher",
            envoye_le=datetime(2026, 9, 22, 9, 0),
            ecriture_ids=(EcritureId("e1"), EcritureId("e2")),
        )
    )
    depot.enregistrer(
        NotificationEnvoyee(
            id="n2",
            dossier_id=DossierId("d-notif"),
            type="a_trancher",
            envoye_le=datetime(2026, 9, 23, 9, 0),
            ecriture_ids=(EcritureId("e3"),),
        )
    )

    derniere = depot.derniere(DossierId("d-notif"), "a_trancher")
    assert derniere is not None
    assert (derniere.id, derniere.ecriture_ids) == ("n2", (EcritureId("e3"),))
    assert [n.id for n in depot.lister(DossierId("d-notif"), limite=5)] == ["n2", "n1"]

    assert depot.marquer_lue(DossierId("d-notif"), "n2", datetime(2026, 9, 24, 8, 0)) is True
    assert depot.marquer_lue(DossierId("d-notif"), "absente", datetime(2026, 9, 24, 8, 0)) is False
    assert depot.marquer_lue(DossierId("d-notif"), "n2", datetime(2026, 9, 24, 8, 30)) is True
    assert depot.marquer_lues(DossierId("d-notif"), datetime(2026, 9, 24, 9, 0)) == 1
    assert depot.marquer_lues(DossierId("d-notif"), datetime(2026, 9, 25, 9, 0)) == 0
    assert {n.id: n.lue_le for n in depot.lister(DossierId("d-notif"), limite=5)} == {
        "n2": datetime(2026, 9, 24, 8, 0),
        "n1": datetime(2026, 9, 24, 9, 0),
    }
