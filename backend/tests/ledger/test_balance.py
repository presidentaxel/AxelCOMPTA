"""Invariant I7 (AXE-807) : les écarts de balance par journal et au total."""

from __future__ import annotations

from axelcompta.core.ids import DossierId
from axelcompta.ledger.balance import Ecart, SoldeJournal, ecarts

A, B = DossierId("a"), DossierId("b")


def test_une_balance_equilibree_n_a_aucun_ecart() -> None:
    assert ecarts([SoldeJournal(A, "BQ", 100, 100), SoldeJournal(A, "OD", 5, 5)]) == []
    assert ecarts([]) == []


def test_un_journal_desequilibre_est_signale_avec_le_total_du_dossier() -> None:
    trouves = ecarts(
        [
            SoldeJournal(A, "BQ", 100, 100),
            SoldeJournal(A, "OD", 12, 10),
            SoldeJournal(B, "BQ", 7, 7),
        ]
    )
    assert trouves == [Ecart(A, "OD", 12, 10), Ecart(A, None, 112, 110)]
    assert "a, journal OD, débit 12 ≠ crédit 10" in trouves[0].message
    assert "a, total" in trouves[1].message
