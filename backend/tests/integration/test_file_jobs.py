"""AXE-845 contre un vrai Postgres : le gestionnaire dépose et suit ses
demandes de synchro (une seule active), le worker propriétaire les exécute ;
les décisions sur les nouveaux contacts sont gardées et immuables."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import contexte_identite
from axelcompta.jobs.file import TYPE_SYNCHRO
from axelcompta.jobs.postgres import FilePostgres
from axelcompta.tenants.contacts_proposes import PropositionStockee
from axelcompta.tenants.contacts_proposes_postgres import PostgresContactsProposes

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _migrer_et_web(engine: Engine, tenant: str) -> Engine:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    with engine.begin() as connexion:
        connexion.execute(text("INSERT INTO tenants (id, nom) VALUES (:t, 'T')"), {"t": tenant})
    return create_engine(
        make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    )


def test_une_seule_demande_active_et_le_worker_l_execute(engine: Engine, id_unique: str) -> None:
    web = _migrer_et_web(engine, id_unique)
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        demandes = FilePostgres(web)
        premiere = demandes.demander(id_unique, TYPE_SYNCHRO)
        seconde = demandes.demander(id_unique, TYPE_SYNCHRO)
        assert premiere.id == seconde.id and premiere.statut == "en_attente"
    with contexte_identite(dossier_id=None, tenant_id="autre"):
        assert FilePostgres(web).dernier(id_unique, TYPE_SYNCHRO) is None  # RLS

    worker = FilePostgres(engine)
    job = worker.prendre("w1")
    assert job is not None and job.id == premiere.id and job.statut == "en_cours"
    worker.terminer(job.id, "3 opérations reçues")
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        fini = FilePostgres(web).dernier(id_unique, TYPE_SYNCHRO)
        assert fini is not None and (fini.statut, fini.resultat) == ("fait", "3 opérations reçues")
        assert FilePostgres(web).demander(id_unique, TYPE_SYNCHRO).id != premiere.id
    web.dispose()


def test_propositions_et_decisions_de_contacts(engine: Engine, id_unique: str) -> None:
    web = _migrer_et_web(engine, id_unique)
    tenant = TenantId(id_unique)
    PostgresContactsProposes(engine).remplacer_propositions(
        tenant,
        [
            PropositionStockee(
                "10",
                "VTC NORD",
                None,
                "SAS",
                date(2026, 3, 13),
                "49.32Z",
                (),
                False,
                datetime.now(UTC),
            )
        ],
    )
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        depot = PostgresContactsProposes(web)
        assert [p.contact_nr for p in depot.propositions(tenant)] == ["10"]
        depot.decider(tenant, "10", "ignorer", "louis", datetime.now(UTC))
        depot.decider(tenant, "10", "ajouter", "louis", datetime.now(UTC))
        assert depot.decisions(tenant) == {"10": "ajouter"}
    web.dispose()
    with engine.begin() as connexion, pytest.raises(DBAPIError):
        connexion.execute(text("UPDATE decisions_contacts SET decision = 'ignorer'"))
