"""AXE-831 : une imputation sépare la TVA déductible estimée."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from axelcompta.core.money import Money
from axelcompta.ledger.models import LigneEcriture, Sens
from axelcompta.packs.tva_deductible import RegleTva
from axelcompta.workflow.tva_imputation import lignes_imputees, tva_affichee

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


JOUR = date(2026, 3, 1)


def _ttc(compte: str, montant: int) -> tuple[LigneEcriture, ...]:
    return (
        LigneEcriture("5121", Sens.CREDIT, Money(montant)),
        LigneEcriture(compte, Sens.DEBIT, Money(montant)),
    )


def test_une_depense_ttc_montre_l_estimation_de_la_table() -> None:
    """Les écritures déjà passées n'ont pas de ligne 44566 : l'écran calcule
    quand même l'estimation, sans la figer."""
    tva = tva_affichee(
        _ttc("6061", 60_00),
        montant_ttc_cts=60_00,
        categorie=None,
        jour=JOUR,
        regime_tva="reel_normal",
    )
    assert tva is not None
    assert (tva.centimes, tva.origine) == (10_00, "estimee")


def test_le_montant_ecrit_reste_celui_de_l_estimation() -> None:
    """Un centime écrit en estimé ne se recalcule pas si la table dirait 10 €."""
    lignes = _ttc("6061", 60_00) + (
        LigneEcriture("44566", Sens.DEBIT, Money(1), code_tva="deductible_estimee_20"),
    )
    tva = tva_affichee(
        lignes, montant_ttc_cts=60_00, categorie="carburant", jour=JOUR, regime_tva="reel_normal"
    )
    assert tva is not None
    assert (tva.centimes, tva.origine) == (1, "estimee")


def test_un_montant_releve_remplace_l_estimation() -> None:
    lignes = (
        LigneEcriture("6061", Sens.DEBIT, Money(52_00), code_tva="deductible_estimee_20"),
        LigneEcriture("44566", Sens.DEBIT, Money(8_00), code_tva="deductible_relevee_20"),
    )
    tva = tva_affichee(
        lignes, montant_ttc_cts=60_00, categorie="carburant", jour=JOUR, regime_tva="reel_normal"
    )
    assert tva is not None
    assert (tva.centimes, tva.origine) == (8_00, "relevee")


def test_la_franchise_n_estime_rien() -> None:
    assert (
        tva_affichee(
            _ttc("6061", 60_00),
            montant_ttc_cts=60_00,
            categorie="carburant",
            jour=JOUR,
            regime_tva="franchise",
        )
        is None
    )
