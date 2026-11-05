from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.core.money import Money
from axelcompta.ingestion.ecritures_settlement import (
    RegimeTvaInconnu,
    RegimeTvaRecettesInconnu,
    construire_ecriture_settlement,
)
from axelcompta.ingestion.providers.base import NormalizedTransaction, PlatformSettlement
from axelcompta.ledger.invariants import solde, verifier_equilibre
from axelcompta.ledger.models import Ecriture, Sens


def _transaction(montant_cts: int) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId("tx1"),
        dossier_id=DossierId("d1"),
        date=date(2026, 9, 3),
        montant_cts=montant_cts,
        libelle="UBER BV",
        source_provider="fixture",
        raw_payload={},
    )


def _settlement(
    gross_cts: int, commission_cts: int, net_cts: int, regime: str, platform: str = "uber"
) -> PlatformSettlement:
    return PlatformSettlement(
        dossier_id=DossierId("d1"),
        platform=platform,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        payout_date=date(2026, 9, 2),
        gross_earnings_cts=gross_cts,
        commission_cts=commission_cts,
        commission_tva_regime=regime,
        net_payout_cts=net_cts,
        currency="EUR",
        source_provider="rollee",
        raw_payload={},
    )


def _montant(ecriture: Ecriture, compte: str, sens: Sens) -> int:
    return next(
        ligne.montant.centimes
        for ligne in ecriture.lignes
        if ligne.compte == compte and ligne.sens is sens
    )


def test_uber_france_reproduit_le_golden_test_doc13_paragraphe_5_3() -> None:
    settlement = _settlement(1_040_00, 192_00, 848_00, "france_20")
    ecriture = construire_ecriture_settlement(_transaction(848_00), settlement, numero=1)

    assert _montant(ecriture, "512", Sens.DEBIT) == 848_00
    assert _montant(ecriture, "622", Sens.DEBIT) == 160_00
    assert _montant(ecriture, "44566", Sens.DEBIT) == 32_00
    assert _montant(ecriture, "706", Sens.CREDIT) == 945_45
    assert _montant(ecriture, "44571", Sens.CREDIT) == 94_55

    debit, credit = solde(ecriture)
    assert debit == credit == Money(104_000)


def test_bolt_autoliquidation_est_equilibree_et_symetrique() -> None:
    settlement = _settlement(500_00, 50_00, 450_00, "autoliquidation_ue", platform="bolt")
    ecriture = construire_ecriture_settlement(_transaction(450_00), settlement, numero=2)

    assert _montant(ecriture, "622", Sens.DEBIT) == 50_00  # déjà HT, pas divisé
    tva_deductible = _montant(ecriture, "44566", Sens.DEBIT)
    montants_44571 = [
        ligne.montant.centimes for ligne in ecriture.lignes if ligne.compte == "44571"
    ]
    assert tva_deductible in montants_44571  # la ligne due symétrique existe et s'annule

    debit, credit = solde(ecriture)
    assert debit == credit


def test_regime_inconnu_leve_une_erreur_explicite() -> None:
    settlement = _settlement(100_00, 10_00, 90_00, "regime_jamais_vu")
    with pytest.raises(RegimeTvaInconnu):
        construire_ecriture_settlement(_transaction(90_00), settlement, numero=1)


def test_franchise_reproduit_le_cas_doc13_paragraphe_5_3() -> None:
    """doc 13 §5.3 « cas franchise » : pas de TVA collectée, commission TTC
    non récupérable — doc 17 §4.3, profil Yanis."""
    settlement = _settlement(1_040_00, 192_00, 848_00, "france_20")
    ecriture = construire_ecriture_settlement(
        _transaction(848_00), settlement, numero=1, tva_recettes_regime="franchise"
    )

    assert _montant(ecriture, "512", Sens.DEBIT) == 848_00
    assert _montant(ecriture, "622", Sens.DEBIT) == 192_00  # TTC, pas de 44566
    assert _montant(ecriture, "706", Sens.CREDIT) == 1_040_00  # brut, pas de TVA
    assert not any(ligne.compte == "44566" for ligne in ecriture.lignes)
    assert not any(ligne.compte == "44571" for ligne in ecriture.lignes)

    debit, credit = solde(ecriture)
    assert debit == credit == Money(104_000)


def test_franchise_avec_autoliquidation_non_couverte() -> None:
    """Combinaison franchise + Bolt (autoliquidation UE) volontairement hors
    scope démo (doc 17 §3) — erreur explicite plutôt qu'un calcul faux."""
    settlement = _settlement(500_00, 50_00, 450_00, "autoliquidation_ue", platform="bolt")
    with pytest.raises(RegimeTvaInconnu):
        construire_ecriture_settlement(
            _transaction(450_00), settlement, numero=1, tva_recettes_regime="franchise"
        )


def test_regime_tva_recettes_inconnu_leve_une_erreur_explicite() -> None:
    settlement = _settlement(100_00, 10_00, 90_00, "france_20")
    with pytest.raises(RegimeTvaRecettesInconnu):
        construire_ecriture_settlement(
            _transaction(90_00), settlement, numero=1, tva_recettes_regime="jamais_vu"
        )


@pytest.mark.parametrize("regime", ["assujetti_taux_reduit", "franchise"])
def test_le_virement_va_au_sous_compte_de_la_banque_qui_l_a_recu(regime: str) -> None:
    """AXE-832 : le settlement crédite le 512x du compte bancaire du virement."""
    settlement = _settlement(1_040_00, 192_00, 848_00, "france_20")
    ecriture = construire_ecriture_settlement(
        _transaction(848_00),
        settlement,
        numero=1,
        tva_recettes_regime=regime,
        compte_banque="5122",
    )
    banques = [ligne for ligne in ecriture.lignes if ligne.compte.startswith("512")]
    assert [ligne.compte for ligne in banques] == ["5122"]
    verifier_equilibre(ecriture)
