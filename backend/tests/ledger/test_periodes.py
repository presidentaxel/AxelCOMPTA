"""Invariant I4 (AXE-806) : périodes closes, refus et date de report."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.filings.fec import exporter_fec
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import (
    PeriodeClose,
    date_de_report,
    periode_close_de,
    verifier_hors_periode_close,
)
from axelcompta.workflow.expert import preparer_imputation

DOSSIER = DossierId("d1")
CLOS_2025 = (date(2025, 1, 1), date(2025, 12, 31))
# Premier exercice long, clos lui aussi : 13/03/2024 → 31/12/2024.
CLOS_2024 = (date(2024, 3, 13), date(2024, 12, 31))


def _ecriture(jour: date) -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=jour,
        libelle="Péage",
        reference_piece=None,
        lignes=(
            LigneEcriture("625", Sens.DEBIT, Money(12_00)),
            LigneEcriture("512", Sens.CREDIT, Money(12_00)),
        ),
    )


def test_periode_close_de() -> None:
    assert periode_close_de(date(2025, 12, 15), [CLOS_2025]) == CLOS_2025
    assert periode_close_de(date(2025, 1, 1), [CLOS_2025]) == CLOS_2025  # bornes incluses
    assert periode_close_de(date(2026, 1, 1), [CLOS_2025]) is None
    assert periode_close_de(date(2025, 6, 1), []) is None


def test_le_refus_dit_quel_exercice_est_clos() -> None:
    with pytest.raises(PeriodeClose, match=r"du 01/01/2025 au 31/12/2025 est clos"):
        verifier_hors_periode_close(date(2025, 12, 15), [CLOS_2025])
    verifier_hors_periode_close(date(2026, 1, 2), [CLOS_2025])


def test_date_de_report() -> None:
    assert date_de_report(date(2026, 2, 1), [CLOS_2025]) == date(2026, 2, 1)
    assert date_de_report(date(2025, 12, 15), [CLOS_2025]) == date(2026, 1, 1)
    # Deux exercices clos qui se suivent : on va au premier jour vraiment ouvert.
    assert date_de_report(date(2024, 5, 1), [CLOS_2024, CLOS_2025]) == date(2026, 1, 1)


def test_le_grand_livre_en_memoire_refuse_une_ecriture_dans_un_exercice_clos() -> None:
    ledger = InMemoryLedgerService()
    ledger.enregistrer(_ecriture(date(2025, 12, 15)))
    ledger.clore(DOSSIER, *CLOS_2025)

    with pytest.raises(PeriodeClose):
        ledger.enregistrer(_ecriture(date(2025, 12, 20)))

    inverse = contrepasser(_ecriture(date(2025, 12, 15)), ledger.periodes_closes(DOSSIER))
    ledger.enregistrer(inverse)
    assert inverse.date == date(2026, 1, 1)
    assert (inverse.journal, inverse.reference_piece) == (Journal.OD, "e1")
    assert ledger.periodes_closes(DossierId("autre")) == ()


def test_sans_periode_close_la_contre_passation_garde_la_date() -> None:
    assert contrepasser(_ecriture(date(2026, 3, 1))).date == date(2026, 3, 1)


def test_le_fec_de_l_exercice_clos_est_identique_a_l_octet_pres_apres_correction() -> None:
    """Critère AXE-806 : une imputation sur 2025 clos ne change pas le FEC 2025."""
    ledger = InMemoryLedgerService()
    origine = dataclasses.replace(
        _ecriture(date(2025, 11, 4)),
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(12_00)),
            LigneEcriture("512", Sens.CREDIT, Money(12_00)),
        ),
    )
    ledger.enregistrer(origine)
    ledger.clore(DOSSIER, *CLOS_2025)

    def fec_2025() -> str:
        return exporter_fec(
            tuple(e for e in ledger.grand_livre(DOSSIER) if CLOS_2025[0] <= e.date <= CLOS_2025[1])
        )

    avant = fec_2025()
    inverse, nouvelle = preparer_imputation(
        origine, "625", {origine.id}, ledger.periodes_closes(DOSSIER)
    )
    ledger.enregistrer(inverse)
    ledger.enregistrer(nouvelle)

    assert fec_2025() == avant
    assert {e.date for e in (inverse, nouvelle)} == {date(2026, 1, 1)}
