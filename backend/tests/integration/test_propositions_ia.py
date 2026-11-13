"""AXE-888 : propositions de l'IA en base, une seule par libellé et par version."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId
from axelcompta.workflow.propositions_ia import PropositionIa
from axelcompta.workflow.propositions_ia_postgres import PostgresPropositionsIa

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 12, 9, tzinfo=UTC)


def test_enregistrer_puis_relire_sans_doublon(
    engine: Engine, creer_dossier: Callable[[str], None]
) -> None:
    creer_dossier("d1")
    depot = PostgresPropositionsIa(engine)
    premiere = PropositionIa(DossierId("d1"), "total", "v1", "carburant", 0.9, "Station", "m", LE)
    depot.enregistrer([premiere])
    depot.enregistrer(
        [PropositionIa(DossierId("d1"), "total", "v1", "repas_et_receptions", 0.5, "", "m", LE)]
    )
    assert depot.lister(DossierId("d1"), "v1") == {"total": premiere}
    assert depot.lister(DossierId("d1"), "v2") == {}
