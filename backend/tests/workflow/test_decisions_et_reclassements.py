"""AXE-852 en mémoire : l'écriture en séquence n'écrit les décisions
qu'après leurs OD, qui portent les contrôles d'invariants."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from axelcompta.categorize.models import Etage
from axelcompta.core.errors import InvariantViole
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_et_reclassements import EnSequence
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository

D = DossierId("d1")
DECISION = DecisionHumaine(
    dossier_id=D,
    ecriture_id=EcritureId("d1:s"),
    categorie="carburant",
    etage_origine=Etage.ML,
    confiance_origine=0.4,
    decide_par=UserId("dirigeant"),
    decide_le=datetime(2026, 11, 9, tzinfo=UTC),
)


def _od(credit: int) -> Ecriture:
    return Ecriture(
        id=EcritureId("d1:s:decision-1"),
        dossier_id=D,
        journal=Journal.OD,
        date=date(2026, 6, 1),
        libelle="Reclassement",
        reference_piece=None,
        lignes=(
            LigneEcriture("6061", Sens.DEBIT, Money(60_00)),
            LigneEcriture("471", Sens.CREDIT, Money(credit)),
        ),
    )


def test_la_decision_suit_son_od() -> None:
    decisions, ledger = InMemoryDecisionRepository(), InMemoryLedgerService()
    EnSequence(decisions, ledger).ecrire([DECISION], [_od(60_00)])
    assert decisions.lister_decisions(D) == (DECISION,)
    assert [e.id for e in ledger.grand_livre(D)] == ["d1:s:decision-1"]


def test_une_od_refusee_n_ecrit_pas_la_decision() -> None:
    decisions, ledger = InMemoryDecisionRepository(), InMemoryLedgerService()
    with pytest.raises(InvariantViole):
        EnSequence(decisions, ledger).ecrire([DECISION], [_od(59_99)])
    assert decisions.lister_decisions(D) == ()
    assert ledger.grand_livre(D) == ()
