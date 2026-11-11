"""AXE-846 : avec le rôle web (celui de l'API en production), le dirigeant
enregistre l'identité de sa société et confirme sa configuration (AXE-730),
dans son seul dossier.

Avant la migration `a3f8c2d71e46`, la confirmation d'AXE-730 échouait en
production : le rôle web n'avait pas l'UPDATE de `forme_juridique` ni
d'`a_confirmer` (« permission denied for table dossiers »), et seuls les
tests en mémoire passaient."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.core.rls import contexte_identite
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.audit import ACTE_IDENTITE
from axelcompta.workflow.orm import journal_audit

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
LE = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def engine_web(engine: Engine) -> Iterator[Engine]:
    """Rôle `axelcompta_web`, après les migrations (rôle, policies, GRANT)."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


@pytest.fixture
def deux_dossiers(engine: Engine, engine_web: Engine) -> PostgresDossierRepository:
    """Karim (SAS à confirmer) et Sophie, sans identité, dans un portefeuille."""
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId("tenant-a"), nom="A"))
    for dossier_id in ("karim", "sophie"):
        depot.enregistrer(
            Dossier(
                id=DossierId(dossier_id),
                tenant_id=TenantId("tenant-a"),
                forme_juridique="SAS",
                regime_imposition="IS",
                regime_tva="franchise",
                nom=dossier_id,
                tva_recettes_regime="franchise",
                exercice_debut=date(2026, 1, 1),
                a_confirmer=("forme_juridique",),
            )
        )
    return depot


def _relu(depot: PostgresDossierRepository, dossier_id: str) -> Dossier:
    dossier = depot.obtenir(DossierId(dossier_id))
    assert dossier is not None
    return dossier


def test_le_dirigeant_enregistre_son_identite_avec_le_role_web(
    engine: Engine, engine_web: Engine, deux_dossiers: PostgresDossierRepository
) -> None:
    with contexte_identite(dossier_id="karim", tenant_id=None):
        PostgresDossierRepository(engine_web).enregistrer_identite(
            DossierId("karim"), IDENTITE_KARIM, UserId("u-karim"), LE
        )
    assert _relu(deux_dossiers, "karim").identite == IDENTITE_KARIM
    with engine.connect() as connexion:
        actes = connexion.execute(
            select(journal_audit.c.type_acte, journal_audit.c.reference).where(
                journal_audit.c.dossier_id == "karim"
            )
        ).all()
    assert (ACTE_IDENTITE, IDENTITE_KARIM.siren) in [tuple(a) for a in actes]


def test_le_dirigeant_confirme_sa_configuration_avec_le_role_web(
    engine_web: Engine, deux_dossiers: PostgresDossierRepository
) -> None:
    confirme = dataclasses.replace(
        _relu(deux_dossiers, "karim"), forme_juridique="SASU", a_confirmer=()
    )
    with contexte_identite(dossier_id="karim", tenant_id=None):
        PostgresDossierRepository(engine_web).confirmer_configuration(confirme, UserId("u"), LE)
    relu = _relu(deux_dossiers, "karim")
    assert (relu.forme_juridique, relu.a_confirmer) == ("SASU", ())


def test_le_role_web_ne_touche_pas_l_identite_d_un_autre_dossier(
    engine_web: Engine, deux_dossiers: PostgresDossierRepository
) -> None:
    with contexte_identite(dossier_id="karim", tenant_id=None), pytest.raises(Introuvable):
        PostgresDossierRepository(engine_web).enregistrer_identite(
            DossierId("sophie"), IDENTITE_KARIM, UserId("u-karim"), LE
        )
    assert _relu(deux_dossiers, "sophie").identite is None
