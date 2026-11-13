"""AXE-887 : lots du LLM et alertes de budget en base."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.db import metadata
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.workflow.budget_llm import Lot
from axelcompta.workflow.lots_llm_postgres import PostgresAlertesLlm, PostgresLotsLlm

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 13, 9, tzinfo=UTC)


def _lot() -> Lot:
    return Lot(
        id="lot-1",
        tenant_id=TenantId("t-test"),
        dossier_id=DossierId("d1"),
        version="v1",
        modele="claude-fable-5-2",
        cles=("BOULANGERIE", "TOTAL"),
        statut="soumis",
        estimation_usd=0.012,
        soumis_le=LE,
    )


def test_un_lot_reserve_puis_releve_est_relu_a_l_identique(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    depot = PostgresLotsLlm(engine)
    depot.enregistrer([_lot()])
    fini = replace(
        _lot(),
        batch_id="msgbatch_1",
        statut="termine",
        cout_usd=0.004,
        jetons_entree=1_000,
        jetons_sortie=200,
        jetons_cache=800,
        termine_le=LE + timedelta(hours=1),
    )
    depot.enregistrer([fini])
    assert depot.lister(LE - timedelta(days=1)) == [fini]
    assert depot.lister(LE + timedelta(minutes=1)) == []


def test_une_alerte_ne_part_qu_une_fois_par_mois(engine: Engine) -> None:
    metadata.create_all(engine)
    alertes = PostgresAlertesLlm(engine)
    assert alertes.marquer("chauffeur", "d1", "2026-11", "50", LE)
    assert not alertes.marquer("chauffeur", "d1", "2026-11", "50", LE)
    assert alertes.marquer("chauffeur", "d1", "2026-12", "50", LE)
