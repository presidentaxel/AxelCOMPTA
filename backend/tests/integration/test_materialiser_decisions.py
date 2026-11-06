"""AXE-420 : reprise des décisions d'avant contre un vrai Postgres."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository

pytestmark = pytest.mark.integration

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "materialiser_decisions.py"
_spec = importlib.util.spec_from_file_location("materialiser_decisions", _SCRIPT)
assert _spec is not None and _spec.loader is not None
materialiser_decisions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(materialiser_decisions)


def test_la_reprise_ecrit_les_decisions_une_seule_fois(
    engine: Engine,
    creer_dossier: Callable[[str], None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    creer_dossier("d1")
    ledger = PostgresLedgerService(engine)
    ledger.enregistrer(
        Ecriture(
            id=EcritureId("d1:s1"),
            dossier_id=DossierId("d1"),
            journal=Journal.BQ,
            date=date(2026, 3, 1),
            libelle="CB TOTAL",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(60_00)),
                LigneEcriture("471", Sens.DEBIT, Money(60_00)),
            ),
        )
    )
    PostgresDecisionRepository(engine).enregistrer_decision(
        DecisionHumaine(
            dossier_id=DossierId("d1"),
            ecriture_id=EcritureId("d1:s1"),
            categorie="carburant",
            etage_origine=Etage.ML,
            confiance_origine=0.5,
            decide_par=UserId("chauffeur"),
            decide_le=datetime(2026, 3, 2, tzinfo=UTC),
        )
    )
    monkeypatch.setattr(sys, "argv", ["x", "--dossier", "d1"])
    materialiser_decisions.main()
    assert "1 reclassement(s) à écrire (simulation)" in capsys.readouterr().out
    assert len(ledger.grand_livre(DossierId("d1"))) == 1  # la simulation n'écrit rien

    monkeypatch.setattr(sys, "argv", ["x", "--dossier", "d1", "--appliquer"])
    materialiser_decisions.main()
    ids = {e.id for e in ledger.grand_livre(DossierId("d1"))}
    assert ids == {"d1:s1", "d1:s1:decision-1"}

    materialiser_decisions.main()  # rejouée : rien de plus
    assert "Total : 0 reclassement(s) écrits." in capsys.readouterr().out.splitlines()[-1]
