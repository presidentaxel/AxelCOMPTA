"""AXE-841 contre un vrai Postgres : le rôle web lit la révision, l'API
refuse de démarrer sur une base en retard."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

import axelcompta.demo_api as demo_api
from axelcompta.api.app import create_app
from axelcompta.core.schema import (
    VARIABLE_SANS_VERIFICATION,
    SchemaEnRetard,
    revision_en_base,
    tete_unique,
)

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


@pytest.fixture
def engine_web(engine: Engine) -> Iterator[Engine]:
    command.upgrade(_config(), "head")
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


def test_la_revision_n_est_pas_masquee_par_la_securite_par_ligne(engine: Engine) -> None:
    """Supabase active la sécurité par ligne sans règle : le rôle web ne
    voyait aucune révision (AXE-841)."""
    command.upgrade(_config(), "head")
    with engine.connect() as connexion:
        masquee = connexion.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'alembic_version'")
        ).scalar()
    assert masquee is False


def test_l_api_demarre_sur_une_base_a_jour_et_refuse_une_base_en_retard(
    engine_web: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(VARIABLE_SANS_VERIFICATION, raising=False)
    monkeypatch.setattr(demo_api, "_ENGINE_DEMO", engine_web)
    assert revision_en_base(engine_web) == tete_unique()  # le rôle web lit la révision

    with TestClient(create_app()) as client:
        assert client.get("/sante").status_code == 200

    command.downgrade(_config(), "-1")
    with pytest.raises(SchemaEnRetard, match="alembic upgrade head"), TestClient(create_app()):
        pass

    monkeypatch.setenv(VARIABLE_SANS_VERIFICATION, "1")
    with TestClient(create_app()) as client:  # poste de dev : vérification sautée
        assert client.get("/sante").status_code == 200
    # Remonte à la tête : une révision qui retire une table (AXE-872 retire
    # `integrations_envoi`) la recréerait sinon, et le nettoyage du test
    # (`metadata.drop_all`) ne pourrait plus supprimer `tenants`.
    command.upgrade(_config(), "head")
