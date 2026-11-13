"""AXE-871 : le contexte d'une décision passe par la base à l'identique."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.workflow.decisions import ContexteDecision, DecisionHumaine
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository

pytestmark = pytest.mark.integration


def test_le_contexte_est_relu_tel_qu_ecrit(
    engine: Engine,
    creer_dossier: Callable[[str], None],
    creer_ecriture: Callable[[str, str], None],
) -> None:
    creer_dossier("d1")
    creer_ecriture("d1", "e1")
    avis = {  # AXE-901
        "synchro": {"etage": "REGLE", "categorie": "carburant", "confiance": 0.95},
        "ia": {"categorie": "carburant", "confiance": 0.8, "justification": "station"},
    }
    contexte = ContexteDecision(
        "CB TOTAL", -1000, "card", "carburant", "REGLE", 0.95, "confirmee", avis
    )
    depot = PostgresDecisionRepository(engine)
    depot.enregistrer_decision(
        DecisionHumaine(
            DossierId("d1"),
            EcritureId("e1"),
            "carburant",
            Etage.REGLE,
            0.95,
            UserId("u1"),
            datetime(2026, 11, 12, 9, tzinfo=UTC),
            contexte,
        )
    )
    (relue,) = depot.lister_decisions(DossierId("d1"))
    assert relue.contexte == contexte
