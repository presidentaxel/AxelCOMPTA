"""AXE-849 : lectures et résolutions en base, avec le rôle web (celui de
l'API) : en ajout seul, limitées au dossier de l'appelant."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.core.rls import contexte_identite
from axelcompta.tenants.models import Dossier, EcartRegistre, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.registres import fiche_rne
from axelcompta.tenants.registres_depot import RegistresPostgres, ResolutionEcart
from tests.tenants.registres_fixtures import RNE_SAS_PLURIPERSONNELLE, SIREN

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
LE = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
ECART = EcartRegistre("forme_juridique", "SASU", "SAS")


@pytest.fixture
def engine_web(engine: Engine) -> Iterator[Engine]:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


@pytest.fixture
def depot(engine: Engine, engine_web: Engine) -> PostgresDossierRepository:
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId("tenant-a"), nom="A"))
    for dossier_id in ("karim", "sophie"):
        depot.enregistrer(
            Dossier(
                id=DossierId(dossier_id),
                tenant_id=TenantId("tenant-a"),
                forme_juridique="SASU",
                regime_imposition="IS",
                regime_tva="reel_normal",
                nom=dossier_id,
                tva_recettes_regime="assujetti_taux_reduit",
                exercice_debut=date(2026, 1, 1),
                siren=SIREN,
            )
        )
    return depot


def _relu(depot: PostgresDossierRepository, dossier_id: str) -> Dossier:
    dossier = depot.obtenir(DossierId(dossier_id))
    assert dossier is not None
    return dossier


def test_lecture_puis_resolution_avec_le_role_web(
    engine: Engine, engine_web: Engine, depot: PostgresDossierRepository
) -> None:
    fiche = fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, date(2026, 11, 10))
    assert fiche is not None
    RegistresPostgres(engine).enregistrer_lecture(_relu(depot, "karim"), fiche, (ECART,))
    assert _relu(depot, "karim").ecarts_registre == (ECART,)
    assert _relu(depot, "karim").siren == SIREN

    web = RegistresPostgres(engine_web)
    with contexte_identite(dossier_id="karim", tenant_id=None):
        lue = web.derniere_lecture(DossierId("karim"))
        assert lue is not None and lue[0] == fiche
        tranche = ResolutionEcart(DossierId("karim"), ECART, "officielle", UserId("u"), LE)
        web.resoudre(tranche, (), "SAS")
        assert web.resolus(DossierId("karim")) == {"forme_juridique": "SAS"}
    apres = _relu(depot, "karim")
    assert (apres.forme_juridique, apres.ecarts_registre) == ("SAS", ())
    with engine.connect() as connexion:
        acte = connexion.execute(
            text("SELECT reference FROM journal_audit WHERE type_acte = 'ecart_registre_tranche'")
        ).scalar_one()
    assert acte == "forme_juridique:officielle"


def test_le_role_web_ne_tranche_pas_le_dossier_d_un_autre(
    engine_web: Engine, depot: PostgresDossierRepository
) -> None:
    web = RegistresPostgres(engine_web)
    tranche = ResolutionEcart(DossierId("sophie"), ECART, "declaree", UserId("u"), LE)
    with (
        contexte_identite(dossier_id="karim", tenant_id=None),
        pytest.raises((Introuvable, DBAPIError)),
    ):
        web.resoudre(tranche, (), None)
    assert _relu(depot, "sophie").forme_juridique == "SASU"


def test_lectures_et_resolutions_ne_se_modifient_pas(
    engine: Engine, depot: PostgresDossierRepository
) -> None:
    fiche = fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, date(2026, 11, 10))
    assert fiche is not None
    RegistresPostgres(engine).enregistrer_lecture(_relu(depot, "karim"), fiche, (ECART,))
    for table in ("lectures_registre",):
        with pytest.raises(DBAPIError), engine.begin() as connexion:
            connexion.execute(text(f"DELETE FROM {table}"))
