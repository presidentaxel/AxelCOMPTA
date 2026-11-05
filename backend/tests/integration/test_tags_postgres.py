"""Tags en Postgres (AXE-829) : même contrat que la mémoire."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.tenants.tags import (
    EXCLUSIONS_PAR_DEFAUT,
    TAGS_PROPOSES,
    Tag,
    TagInvalide,
    etat_du_portefeuille,
)
from axelcompta.tenants.tags_postgres import PostgresTagsRepository

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 5, tzinfo=UTC)
LOUIS = UserId("louis")


def test_poser_retirer_regler(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    tenant = TenantId("t-test")  # le tenant de `creer_dossier`
    depot = PostgresTagsRepository(engine)

    assert set(TAGS_PROPOSES) <= {t.nom for t in depot.lister_tags(tenant)}
    with pytest.raises(TagInvalide):
        depot.poser(tenant, dossier, "inconnu", LOUIS, LE)
    depot.creer_tag(Tag(tenant, "flotte_nord", "Flotte du nord"))
    depot.poser(tenant, dossier, "flotte_nord", LOUIS, LE)
    depot.poser(tenant, dossier, "societe_du_gestionnaire", LOUIS, LE)
    assert etat_du_portefeuille(depot, tenant).exclu(dossier, "synchro")

    depot.retirer(tenant, dossier, "societe_du_gestionnaire", LOUIS, LE)
    depot.regler_exclusion(tenant, "expert", frozenset({"flotte_nord"}), LOUIS, LE)

    etat = etat_du_portefeuille(depot, tenant)
    assert etat.tags_de(dossier) == frozenset({"flotte_nord"})
    assert not etat.exclu(dossier, "synchro")
    assert etat.exclu(dossier, "expert")
    assert depot.exclusions(tenant)["synchro"] == EXCLUSIONS_PAR_DEFAUT["synchro"]
