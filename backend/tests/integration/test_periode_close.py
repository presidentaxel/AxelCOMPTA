"""Invariant I4 en base (migration `f1a6c3e9d257`, AXE-806) : une écriture
datée dans un exercice clos est refusée, même par la connexion propriétaire
qui contourne le domaine."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import PeriodeClose
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.exercices import ExerciceClos
from axelcompta.tenants.exercices_postgres import PostgresExerciceRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _ecriture(dossier_id: str, identifiant: str, jour: date) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=DossierId(dossier_id),
        journal=Journal.BQ,
        date=jour,
        libelle="Péage",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte="625", sens=Sens.DEBIT, montant=Money(12_00)),
            LigneEcriture(compte="512", sens=Sens.CREDIT, montant=Money(12_00)),
        ),
    )


@pytest.fixture
def dossier_2025_clos(engine: Engine, id_unique: str) -> str:
    command.upgrade(_config(), "head")
    depot = PostgresDossierRepository(engine)
    depot.enregistrer_tenant(Tenant(id=TenantId("t-i4"), nom="T"))
    depot.enregistrer(
        Dossier(
            id=DossierId(id_unique),
            tenant_id=TenantId("t-i4"),
            forme_juridique="SASU",
            regime_imposition="IS",
            regime_tva="franchise",
            nom="I4",
            tva_recettes_regime="franchise",
            exercice_debut=date(2025, 1, 1),
        )
    )
    # Écrite avant la clôture : elle reste au grand livre 2025.
    PostgresLedgerService(engine).enregistrer(
        _ecriture(id_unique, f"{id_unique}:e1", date(2025, 12, 15))
    )
    PostgresExerciceRepository(engine).enregistrer(
        ExerciceClos(
            dossier_id=DossierId(id_unique),
            debut=date(2025, 1, 1),
            fin=date(2025, 12, 31),
            clos_le=datetime(2026, 1, 10),
            clos_par="test",
        )
    )
    return id_unique


def test_le_domaine_refuse_et_la_base_aussi(engine: Engine, dossier_2025_clos: str) -> None:
    ledger = PostgresLedgerService(engine)
    tardive = _ecriture(dossier_2025_clos, f"{dossier_2025_clos}:e2", date(2025, 12, 15))
    with pytest.raises(PeriodeClose):
        ledger.enregistrer(tardive)
    with engine.begin() as connexion, pytest.raises(IntegrityError, match="I4"):
        connexion.execute(
            text(
                "INSERT INTO ecritures (id, dossier_id, journal, date, libelle) "
                "VALUES (:id, :d, 'BQ', '2025-12-15', 'directe')"
            ),
            {"id": f"{dossier_2025_clos}:e3", "d": dossier_2025_clos},
        )


def test_une_contre_passation_est_reportee_au_premier_jour_ouvert(
    engine: Engine, dossier_2025_clos: str
) -> None:
    ledger = PostgresLedgerService(engine)
    assert ledger.periodes_closes(DossierId(dossier_2025_clos)) == (
        (date(2025, 1, 1), date(2025, 12, 31)),
    )
    (originale,) = ledger.grand_livre(DossierId(dossier_2025_clos))
    inverse = contrepasser(originale, ledger.periodes_closes(DossierId(dossier_2025_clos)))

    ledger.enregistrer(inverse)

    assert inverse.date == date(2026, 1, 1)
    assert inverse.journal is Journal.OD and inverse.reference_piece == str(originale.id)
    # L'exercice clos n'a pas bougé : une seule écriture datée de 2025.
    dates = [e.date.year for e in ledger.grand_livre(DossierId(dossier_2025_clos))]
    assert sorted(dates) == [2025, 2026]
