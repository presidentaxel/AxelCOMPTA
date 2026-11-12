from __future__ import annotations

from datetime import date

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Sens
from axelcompta.workflow.auto_accept import construire_ecriture_categorisee


def _transaction(montant_cts: int) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId("tx1"),
        dossier_id=DossierId("d1"),
        date=date(2026, 9, 3),
        montant_cts=montant_cts,
        libelle="TOTAL ACCESS A6",
        source_provider="fixture",
        raw_payload={},
    )


def _proposition(categorie: str) -> ProposedEntry:
    return ProposedEntry(
        dossier_id=DossierId("d1"),
        transaction_id=TransactionId("tx1"),
        categorie=categorie,
        etage=Etage.REGLE,
        confiance=0.95,
    )


def test_depense_credite_la_banque_et_debite_le_compte_de_charge() -> None:
    ecriture = construire_ecriture_categorisee(
        _transaction(-45_00), _proposition("carburant"), compte="6061", numero=1
    )
    verifier_equilibre(ecriture)  # ne lève pas : toujours équilibrée par construction
    ligne_512 = next(ligne for ligne in ecriture.lignes if ligne.compte == "512")
    ligne_charge = next(ligne for ligne in ecriture.lignes if ligne.compte == "6061")
    assert ligne_512.sens is Sens.CREDIT
    assert ligne_charge.sens is Sens.DEBIT
    assert ligne_512.montant.centimes == ligne_charge.montant.centimes == 45_00


def test_recette_debite_la_banque_et_credite_le_compte_de_produit() -> None:
    ecriture = construire_ecriture_categorisee(
        _transaction(100_00), _proposition("subventions"), compte="741", numero=2
    )
    verifier_equilibre(ecriture)
    ligne_512 = next(ligne for ligne in ecriture.lignes if ligne.compte == "512")
    assert ligne_512.sens is Sens.DEBIT


def test_le_libelle_est_celui_de_la_banque_sans_la_categorie() -> None:
    """AXE-848 : la catégorie est dans la proposition enregistrée, plus dans
    le libellé (elle finissait dans le FEC)."""
    ecriture = construire_ecriture_categorisee(
        _transaction(-45_00), _proposition("carburant"), compte="6061", numero=1
    )
    assert ecriture.libelle == "TOTAL ACCESS A6"


def test_la_tva_separee_remonte_dans_la_ca3() -> None:
    """AXE-831 : la CA3 du mois montre une TVA déductible non nulle."""
    from axelcompta.closing.tva_periodique import ca3_periode, periodes
    from axelcompta.packs.tva_deductible import regle_tva

    regle = regle_tva("carburant", date(2026, 9, 3), "reel_normal")
    ecriture = construire_ecriture_categorisee(
        _transaction(-60_00), _proposition("carburant"), "6061", 1, regle_tva=regle
    )
    verifier_equilibre(ecriture)
    (septembre,) = [
        p
        for p in periodes(date(2026, 1, 1), date(2026, 12, 31), "mensuelle")
        if p.contient(date(2026, 9, 3))
    ]
    assert ca3_periode([ecriture], septembre).deductible == 10_00
