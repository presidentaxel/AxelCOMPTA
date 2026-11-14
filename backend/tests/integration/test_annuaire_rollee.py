"""AXE-919 : l'annuaire Rollee en base, écrit par le propriétaire, lu sous la RLS."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import contexte_identite
from axelcompta.ingestion.annuaire_rollee import FicheAnnuaire
from axelcompta.ingestion.annuaire_rollee_postgres import PostgresAnnuaireRollee
from axelcompta.tenants.models import Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 14, 9, tzinfo=UTC)
T = TenantId("t-test")
AUTRE = TenantId("t-autre")


BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def engine_web(engine: Engine) -> Iterator[Engine]:
    """Les droits du rôle web viennent des migrations, pas de `metadata`."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


def _fiche(user: str, tenant: TenantId, branchement: str = "b1") -> FicheAnnuaire:
    return FicheAnnuaire(
        user, tenant, branchement, "Élodie Martin", ("bolt.eu-rev",), "e•••n@x.fr", LE
    )


def test_remplacer_lire_et_isoler_les_portefeuilles(engine: Engine, engine_web: Engine) -> None:
    portefeuilles = PostgresDossierRepository(engine)
    for tenant in (T, AUTRE):
        portefeuilles.enregistrer_tenant(Tenant(id=tenant, nom=str(tenant)))
    proprietaire = PostgresAnnuaireRollee(engine)
    proprietaire.remplacer(T, "b1", [_fiche("u1", T), _fiche("u2", T)])
    proprietaire.remplacer(AUTRE, "b9", [_fiche("u9", AUTRE, "b9")])
    proprietaire.remplacer(T, "b1", [_fiche("u1", T)])  # u2 a quitté le compte Rollee
    proprietaire.remplacer(T, "b1", [_fiche("u3", T)], partiel=True)
    assert {f.rollee_user_id for f in proprietaire.fiches(T)} == {"u1", "u3"}
    assert proprietaire.fiche(T, "u1") == _fiche("u1", T)

    web = PostgresAnnuaireRollee(engine_web)
    with contexte_identite(None, str(T)):
        assert {f.rollee_user_id for f in web.fiches(T)} == {"u1", "u3"}
        assert web.fiche(AUTRE, "u9") is None  # la RLS cache l'autre portefeuille
    with contexte_identite(None, str(T)), pytest.raises(Exception, match="permission denied"):
        web.remplacer(T, "b1", [])
