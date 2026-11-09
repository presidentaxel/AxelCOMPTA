"""AXE-424 contre un vrai Postgres : une résolution par entrée, immuable ;
le rôle web lit la quarantaine de son portefeuille."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import contexte_identite
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.workflow.quarantaine import ResolutionRefusee
from axelcompta.workflow.resolutions_quarantaine import Resolution
from axelcompta.workflow.resolutions_quarantaine_postgres import PostgresResolutions

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def test_une_resolution_par_entree_et_la_quarantaine_lue_par_le_role_web(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    creer_dossier("d1")
    PostgresJournalIngestion(engine).mettre_en_quarantaine(
        DossierId("d1"), "digifactory", "supprimee_apres_comptabilisation", "t1", {"id": "t1"}
    )
    web = create_engine(
        make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    )
    with contexte_identite(dossier_id="d1", tenant_id=None):
        (entree,) = PostgresJournalIngestion(web).lister_quarantaine(DossierId("d1"))
        depot = PostgresResolutions(web)
        resolution = Resolution(
            DossierId("d1"), entree.id, "accepter", (), "louis@exemple.fr", datetime.now(UTC)
        )
        depot.enregistrer(resolution)
        with pytest.raises(ResolutionRefusee):
            depot.enregistrer(resolution)
        assert depot.lister(DossierId("d1"))[entree.id].decision == "accepter"
    web.dispose()
    with engine.begin() as connexion, pytest.raises(DBAPIError):
        connexion.execute(text("UPDATE resolutions_quarantaine SET decision = 'ignorer'"))
