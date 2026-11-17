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
from axelcompta.jobs.file import TYPE_RAPPROCHEMENT_ROLLEE, TYPE_SYNCHRO
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


def test_une_demande_pendant_un_job_en_cours_n_est_pas_perdue(
    engine: Engine, id_unique: str
) -> None:
    """AXE-921, contre la vraie base et son index unique partiel."""
    web = _migrer_et_web(engine, id_unique)
    worker = FilePostgres(engine)
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        premiere = FilePostgres(web).demander(id_unique, TYPE_SYNCHRO)
    pris = worker.prendre("w1")
    assert pris is not None and pris.id == premiere.id
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        demandes = FilePostgres(web)
        seconde = demandes.demander(id_unique, TYPE_SYNCHRO)
        assert seconde.id != premiere.id and seconde.statut == "en_attente"
        assert demandes.demander(id_unique, TYPE_SYNCHRO).id == seconde.id
        a = demandes.demander(id_unique, TYPE_RAPPROCHEMENT_ROLLEE, '{"dossier_id": "A"}')
        b = demandes.demander(id_unique, TYPE_RAPPROCHEMENT_ROLLEE, '{"dossier_id": "B"}')
        assert a.id != b.id and a.payload == '{"dossier_id": "A"}'
    worker.terminer(pris.id, "fini")
    suivant = worker.prendre("w1")
    assert suivant is not None and suivant.id == seconde.id
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


def test_un_job_en_echec_ne_double_pas_une_demande_qui_attend(
    engine: Engine, id_unique: str
) -> None:
    """Un job qui échoue repasse en attente, sauf si la même demande attend
    déjà : elle refera le travail (sinon l'index unique ferait planter le worker)."""
    web = _migrer_et_web(engine, id_unique)
    worker = FilePostgres(engine)
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        FilePostgres(web).demander(id_unique, TYPE_SYNCHRO)
    pris = worker.prendre("w1")
    assert pris is not None
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        attend = FilePostgres(web).demander(id_unique, TYPE_SYNCHRO)
    assert worker.echouer(pris.id, "Digifactory indisponible") is True
    with engine.connect() as connexion:
        lignes = connexion.execute(
            text("SELECT id, statut FROM jobs WHERE tenant_id = :t"), {"t": id_unique}
        ).all()
    statuts = {str(ligne.id): str(ligne.statut) for ligne in lignes}
    assert statuts == {pris.id: "echec", attend.id: "en_attente"}
    web.dispose()


def test_un_job_abandonne_est_relache(engine: Engine, id_unique: str) -> None:
    """AXE-958 : un job pris depuis plus de deux heures (worker tué) repart
    en attente avec son motif ; un job pris à l'instant n'est pas touché."""
    web = _migrer_et_web(engine, id_unique)
    with contexte_identite(dossier_id=None, tenant_id=id_unique):
        vieux = FilePostgres(web).demander(id_unique, TYPE_SYNCHRO)
        recent = FilePostgres(web).demander(id_unique, TYPE_RAPPROCHEMENT_ROLLEE)
    worker = FilePostgres(engine)
    assert worker.prendre("w1") is not None
    assert worker.prendre("w1") is not None
    with engine.begin() as connexion:
        connexion.execute(
            text("UPDATE jobs SET pris_le = now() - interval '3 hours' WHERE id = :id"),
            {"id": vieux.id},
        )

    assert worker.relacher_abandonnes() == [vieux.id]

    with engine.connect() as connexion:
        lignes = {
            ligne.id: (ligne.statut, ligne.derniere_erreur)
            for ligne in connexion.execute(
                text("SELECT id, statut, derniere_erreur FROM jobs WHERE tenant_id = :t"),
                {"t": id_unique},
            )
        }
    assert lignes[vieux.id][0] == "en_attente"
    assert (lignes[vieux.id][1] or "").startswith("Abandonné")
    assert lignes[recent.id] == ("en_cours", None)
    web.dispose()
