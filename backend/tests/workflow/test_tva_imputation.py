"""AXE-831 : une imputation sépare la TVA déductible estimée."""

from __future__ import annotations

from decimal import Decimal

from axelcompta.core.money import Money
from axelcompta.ledger.models import LigneEcriture, Sens
from axelcompta.packs.tva_deductible import RegleTva
from axelcompta.workflow.tva_imputation import lignes_imputees

VINGT = RegleTva(taux=Decimal("20"), recuperable=100)


def test_le_compte_puis_la_tva_pour_le_total_exact() -> None:
    lignes = lignes_imputees("6061", Sens.DEBIT, Money(60_00), VINGT)
    assert lignes == (
        LigneEcriture("6061", Sens.DEBIT, Money(50_00), code_tva="deductible_estimee_20"),
        LigneEcriture("44566", Sens.DEBIT, Money(10_00), code_tva="deductible_estimee_20"),
    )


def test_sans_regle_une_seule_ligne() -> None:
    assert lignes_imputees("6257", Sens.DEBIT, Money(25_00), None) == (
        LigneEcriture("6257", Sens.DEBIT, Money(25_00)),
    )


def test_un_centime_ne_contient_pas_de_tva() -> None:
    assert lignes_imputees("6061", Sens.DEBIT, Money(1), VINGT) == (
        LigneEcriture("6061", Sens.DEBIT, Money(1)),
    )
