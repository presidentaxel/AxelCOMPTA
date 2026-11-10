"""AXE-804 : la reprise du bilan d'ouverture s'écrit tout ou rien, avec le
rôle web, une seule fois par dossier."""

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

from axelcompta.closing.ouverture_depot import (
    OuvertureDejaFaite,
    OuvertureImportee,
    OuverturesPostgres,
)
from axelcompta.closing.ouverture_fec import analyser
from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.core.rls import contexte_identite
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from tests.closing.fec_externe import NOM, SIREN, fec

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
OUVERTURE = date(2026, 1, 1)


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
    depot.enregistrer(
        Dossier(
            id=DossierId("reprise"),
            tenant_id=TenantId("tenant-a"),
            forme_juridique="SASU",
            regime_imposition="IS",
            regime_tva="reel_normal",
            nom="reprise",
            tva_recettes_regime="assujetti_taux_reduit",
            exercice_debut=OUVERTURE,
        )
    )
    return depot


def _ouverture(deficits: int = 1200) -> tuple[OuvertureImportee, Ecriture]:
    analyse = analyser(
        fec().encode(), NOM, DossierId("reprise"), SIREN, OUVERTURE, {}, date(2026, 11, 10)
    )
    assert analyse.a_nouveaux is not None
    ouverture = OuvertureImportee(
        dossier_id=DossierId("reprise"),
        nom_fichier=NOM,
        empreinte=analyse.empreinte,
        cloture=analyse.cloture,
        ouverture=OUVERTURE,
        role="dirigeant",
        par=UserId("u"),
        auteur_nom=None,
        motif=None,
        attestation=analyse.attestation,
        correspondance={},
        deficits_euros=deficits,
        ecriture_id=analyse.a_nouveaux.id,
        le=datetime(2026, 11, 10, tzinfo=UTC),
    )
    return ouverture, analyse.a_nouveaux


def test_reprise_avec_le_role_web_tout_ou_rien_puis_verrouillee(
    engine: Engine, engine_web: Engine, depot: PostgresDossierRepository
) -> None:
    ouverture, a_nouveaux = _ouverture()
    with contexte_identite(dossier_id="reprise", tenant_id=None):
        OuverturesPostgres(engine_web).importer(ouverture, a_nouveaux)
        with pytest.raises(OuvertureDejaFaite):
            OuverturesPostgres(engine_web).importer(ouverture, a_nouveaux)
    relu = depot.obtenir(DossierId("reprise"))
    assert relu is not None and relu.deficits_anterieurs_euros == 1200
    ids = {e.id for e in PostgresLedgerService(engine).grand_livre(DossierId("reprise"))}
    assert ouverture.ecriture_id in ids
    lue = OuverturesPostgres(engine).obtenir(DossierId("reprise"))
    assert lue is not None and lue.empreinte == ouverture.empreinte
    with pytest.raises(DBAPIError), engine.begin() as connexion:
        connexion.execute(text("DELETE FROM ouvertures_importees"))


def test_un_autre_dossier_ne_peut_pas_etre_repris_par_ce_role_web(
    engine: Engine, engine_web: Engine, depot: PostgresDossierRepository
) -> None:
    ouverture, a_nouveaux = _ouverture()
    with contexte_identite(dossier_id="autre", tenant_id=None), pytest.raises(DBAPIError):
        OuverturesPostgres(engine_web).importer(ouverture, a_nouveaux)
    assert OuverturesPostgres(engine).obtenir(DossierId("reprise")) is None
