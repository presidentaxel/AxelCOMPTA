from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.expert import ImputationRefusee, preparer_imputation

DOSSIER = DossierId("d1")


def _attente() -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 3, 2),
        libelle="ZARA",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(68_00)),
            LigneEcriture("471", Sens.DEBIT, Money(68_00)),
        ),
    )


def test_une_ecriture_validee_est_contrepassee_puis_reposee() -> None:
    origine = _attente()
    inverse, nouvelle = preparer_imputation(origine, "606", {origine.id})
    assert inverse.id == "e1:contrepassation"
    assert nouvelle.id == "e1:impute-606"
    assert nouvelle.lignes[0].compte == "512"
    assert nouvelle.lignes[1].compte == "606"
    assert nouvelle.lignes[1].montant.centimes == 68_00
    ledger = InMemoryLedgerService()
    ledger.enregistrer(origine)
    ledger.enregistrer(inverse)
    ledger.enregistrer(nouvelle)
    assert {e.id for e in ledger.grand_livre(DOSSIER)} == {origine.id, inverse.id, nouvelle.id}


def test_un_compte_banque_ou_deja_tenu_est_refuse() -> None:
    origine = _attente()
    with pytest.raises(ImputationRefusee):
        preparer_imputation(origine, "512", {origine.id})
    with pytest.raises(ImputationRefusee):
        preparer_imputation(origine, "471", {origine.id})


def test_une_imputation_sur_un_exercice_clos_est_une_od_au_premier_jour_ouvert() -> None:
    """AXE-806 : l'écriture de 2025 ne bouge pas ; la correction est en 2026."""
    origine = dataclasses.replace(_attente(), date=date(2025, 11, 4))
    clos = ((date(2025, 1, 1), date(2025, 12, 31)),)

    inverse, nouvelle = preparer_imputation(origine, "606", {origine.id}, clos)

    assert inverse.date == nouvelle.date == date(2026, 1, 1)
    assert nouvelle.journal is Journal.OD
    assert nouvelle.reference_piece == inverse.reference_piece == str(origine.id)
