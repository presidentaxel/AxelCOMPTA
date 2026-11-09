"""Cache de la file expert (AXE-824) : recalculé quand le dossier change,
et seulement alors. Les triggers sont ceux des migrations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.demo_api import prechauffer_caches
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.file_expert_cache_postgres import PostgresCacheFileExpert

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _ecriture(dossier: str, numero: int) -> Ecriture:
    return Ecriture(
        id=EcritureId(f"{dossier}:e{numero}"),
        dossier_id=DossierId(dossier),
        journal=Journal.BQ,
        date=date(2026, 3, numero),
        libelle="PAIEMENT INCONNU",
        reference_piece=None,
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(12_00)),
            LigneEcriture("512", Sens.CREDIT, Money(12_00)),
        ),
    )


def test_seul_un_dossier_qui_a_change_est_recalcule(engine: Engine, id_unique: str) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId(id_unique), nom="T"))
    dossier = Dossier(
        id=DossierId(id_unique),
        tenant_id=TenantId(id_unique),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="Cache",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 1),
    )
    depot.enregistrer(dossier)
    ledger = PostgresLedgerService(engine)
    ledger.enregistrer(_ecriture(id_unique, 1))

    assert prechauffer_caches(engine, [dossier]) == 1
    (garde,) = PostgresCacheFileExpert(engine).lire([dossier.id]).values()
    assert [s["nature"] for s in garde.sujets] == ["a_trancher"]
    assert prechauffer_caches(engine, [dossier]) == 0  # rien n'a changé

    ledger.enregistrer(_ecriture(id_unique, 2))
    assert prechauffer_caches(engine, [dossier]) == 1
    (garde,) = PostgresCacheFileExpert(engine).lire([dossier.id]).values()
    assert len(garde.sujets) == 2

    # Un justificatif change les sujets (ticket manquant) : il périme aussi.
    with engine.begin() as connexion:
        connexion.execute(
            text(
                "INSERT INTO justificatifs (tenant_id, dossier_id, ecriture_id, empreinte, "
                "extension, taille_octets, contenu) VALUES (:t, :d, :e, 'x', 'jpg', 1, '\\x00')"
            ),
            {"t": id_unique, "d": id_unique, "e": f"{id_unique}:e1"},
        )
    assert prechauffer_caches(engine, [dossier]) == 1
