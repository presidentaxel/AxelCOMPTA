"""AXE-952 contre un vrai Postgres : la synchro donne une fiche à chaque
dossier, une fois."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.fiches_import_portefeuille import completer_fiches
from axelcompta.tenants.fiches_import import nouvelle_fiche
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport
from axelcompta.tenants.postgres import PostgresDossierRepository

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)


def _siren_valide(graine: int) -> str:
    """Huit chiffres tirés de la graine, puis la clé de Luhn."""
    debut = f"9{graine % 10_000_000:07d}"
    somme = 0
    for i, chiffre in enumerate(reversed(debut)):
        n = int(chiffre) * (2 if i % 2 == 0 else 1)
        somme += n - 9 if n > 9 else n
    return debut + str((10 - somme % 10) % 10)


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


def test_une_fiche_complete_sans_dossier_le_fait_creer_par_la_synchro(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    """AXE-974 : le rôle propriétaire de la synchro et du worker crée le
    dossier d'une fiche active complète, et la relie ; rejouer ne crée rien
    de plus. Une fiche ignorée n'en crée pas."""
    creer_dossier(id_unique)  # crée le portefeuille t-test
    tenant = TenantId("t-test")
    depot = PostgresFichesImport(engine)
    siren = _siren_valide(int(id_unique[-6:], 16))
    champs = {
        "siren": siren,
        "denomination": "SOW FAMILY",
        "forme_juridique": "SAS",
        "exercice_debut": "2026-01-01",
        "exercice_fin": "2026-12-31",
    }
    active = dataclasses.replace(
        nouvelle_fiche(f"f-{id_unique}", tenant, "Sow", "Aliou", siren, "b", LE), champs=champs
    )
    ignoree = dataclasses.replace(
        active, id=f"i-{id_unique}", champs={**champs, "siren": "552100554"}, statut="ignore"
    )
    depot.enregistrer(active)
    depot.enregistrer(ignoree)

    premier = completer_fiches(engine, tenant, None, LE)
    second = completer_fiches(engine, tenant, None, LE)

    reliee = depot.lire(tenant, active.id)
    assert reliee.dossier_id is not None
    assert PostgresDossierRepository(engine).obtenir(DossierId(reliee.dossier_id)) is not None
    assert depot.lire(tenant, ignoree.id).dossier_id is None
    assert "1 dossier(s) créé(s) depuis Imports" in premier
    assert "dossier(s) créé(s)" not in second
