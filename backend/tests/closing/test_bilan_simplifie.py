from __future__ import annotations

from datetime import date

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

DOSSIER = DossierId("d1")


def _ledger_avec_le_golden_test_doc17() -> InMemoryLedgerService:
    # Reproduit le golden test doc 13 §5.3 sans passer par le générateur de
    # settlement : ce test vérifie la clôture, pas la ventilation TVA elle-même
    # (déjà couverte par tests/ingestion/test_ecritures_settlement.py).
    ledger = InMemoryLedgerService()
    ledger.enregistrer(
        Ecriture(
            id=EcritureId("e1"),
            dossier_id=DOSSIER,
            journal=Journal.BQ,
            date=date(2026, 9, 3),
            libelle="Règlement Uber",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.DEBIT, Money(848_00)),
                LigneEcriture("622", Sens.DEBIT, Money(160_00)),
                LigneEcriture("44566", Sens.DEBIT, Money(32_00)),
                LigneEcriture("706", Sens.CREDIT, Money(945_45)),
                LigneEcriture("44571", Sens.CREDIT, Money(94_55)),
            ),
        )
    )
    return ledger


def test_cloture_simplifiee_calcule_le_resultat_et_le_bilan() -> None:
    liasse = ClotureSimplifieeService(_ledger_avec_le_golden_test_doc17()).cloturer(
        DOSSIER, exercice="2026"
    )
    assert liasse.cases["CA_HT"] == 945_45
    assert liasse.cases["CHARGES"] == 160_00
    assert liasse.cases["RESULTAT"] == 785_45
    assert liasse.cases["TRESORERIE"] == 848_00
    assert liasse.cases["TVA_A_PAYER"] == 62_55
    assert liasse.cases["2065"] == liasse.cases["RESULTAT"]
    assert liasse.cases["IMMOBILISATIONS"] == 0
    assert liasse.cases["CAPITAUX"] == 0
    assert liasse.cases["COMPTES_NON_VENTILES"] == 0


def test_le_bilan_est_equilibre_tresorerie_egale_resultat_plus_tva() -> None:
    # Golden test de sortie (doc 17 §7bis / semaine 3) : dans notre bilan
    # réduit (pas de capital ni d'autres tiers), la trésorerie doit égaler
    # exactement résultat + TVA à payer.
    liasse = ClotureSimplifieeService(_ledger_avec_le_golden_test_doc17()).cloturer(
        DOSSIER, exercice="2026"
    )
    assert liasse.cases["TRESORERIE"] == liasse.cases["RESULTAT"] + liasse.cases["TVA_A_PAYER"]


def test_cloture_sur_dossier_vide() -> None:
    liasse = ClotureSimplifieeService(InMemoryLedgerService()).cloturer(DOSSIER, exercice="2026")
    assert liasse.cases["RESULTAT"] == 0
    assert liasse.cases["TRESORERIE"] == 0
    assert liasse.cases["IMMOBILISATIONS"] == 0
    assert liasse.cases["CAPITAUX"] == 0
    assert liasse.cases["COMPTES_NON_VENTILES"] == 0


def _ajouter(
    ledger: InMemoryLedgerService, identifiant: str, lignes: tuple[LigneEcriture, ...]
) -> None:
    ledger.enregistrer(
        Ecriture(
            id=EcritureId(identifiant),
            dossier_id=DOSSIER,
            journal=Journal.BQ,
            date=date(2026, 9, 4),
            libelle=identifiant,
            reference_piece=None,
            lignes=lignes,
        )
    )


def test_equilibre_avec_capital_immobilisation_et_compte_non_ventile() -> None:
    """1013 et 218 sont produits par le pipeline (apport, véhicule).
    401 n'a pas de ligne propre : il reste dans COMPTES_NON_VENTILES."""
    ledger = _ledger_avec_le_golden_test_doc17()
    _ajouter(
        ledger,
        "capital",
        (
            LigneEcriture("512", Sens.DEBIT, Money(100_000_00)),
            LigneEcriture("1013", Sens.CREDIT, Money(100_000_00)),
        ),
    )
    _ajouter(
        ledger,
        "vehicule",
        (
            LigneEcriture("218", Sens.DEBIT, Money(40_000_00)),
            LigneEcriture("512", Sens.CREDIT, Money(40_000_00)),
        ),
    )
    _ajouter(
        ledger,
        "fournisseur",
        (
            LigneEcriture("401", Sens.DEBIT, Money(5_000_00)),
            LigneEcriture("512", Sens.CREDIT, Money(5_000_00)),
        ),
    )
    cases = ClotureSimplifieeService(ledger).cloturer(DOSSIER, exercice="2026").cases
    assert cases["CAPITAUX"] == 100_000_00
    assert cases["IMMOBILISATIONS"] == 40_000_00
    assert cases["COMPTES_NON_VENTILES"] == 5_000_00
    assert cases["TRESORERIE"] == 848_00 + 100_000_00 - 40_000_00 - 5_000_00
    assert (
        cases["TRESORERIE"] + cases["IMMOBILISATIONS"] + cases["COMPTES_NON_VENTILES"]
        == cases["RESULTAT"] + cases["TVA_A_PAYER"] + cases["CAPITAUX"]
    )
