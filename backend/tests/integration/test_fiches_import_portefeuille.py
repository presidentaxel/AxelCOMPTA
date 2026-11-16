"""AXE-952 contre un vrai Postgres : la synchro donne une fiche à chaque
dossier, une fois."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.fiches_import_portefeuille import completer_fiches
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def test_chaque_dossier_recoit_sa_fiche_une_seule_fois(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    tenant = TenantId("t-test")  # le portefeuille de `creer_dossier`

    premier = completer_fiches(engine, tenant, None, LE)
    completer_fiches(engine, tenant, None, LE)  # rejouer n'en crée pas une autre

    sienne = [f for f in PostgresFichesImport(engine).toutes(tenant) if f.dossier_id == id_unique]
    assert len(sienne) == 1
    assert sienne[0].champs["denomination"] == "Test"
    assert "créée" in premier
