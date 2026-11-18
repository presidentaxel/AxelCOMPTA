"""AXE-833 : ce qui part en comptabilité depuis les relevés d'une fiche."""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import CompteBancaire
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.releves_en_compta import (
    CompteAEcrire,
    premiere_operation_digifactory,
    transactions,
)
from axelcompta.traitement_documents_import import OperationQif

D = DossierId("DIGI_24951")


def test_deux_releves_qui_se_recouvrent_comptent_une_operation_une_fois() -> None:
    compte = CompteBancaire(D, "67499359", "5121", "Bred", retenu=True)
    a_ecrire = CompteAEcrire(compte, date(2026, 1, 1), date(2026, 6, 1), ("a", "b"))
    uber = OperationQif(date(2026, 3, 2), 120_000, "VIR UBER")
    frais = OperationQif(date(2026, 5, 31), -2_000, "FRAIS")
    lot = transactions(D, a_ecrire, [("a", [uber, uber]), ("b", [uber, frais])])
    assert [(t.date, t.montant_cts) for t in lot] == [
        (date(2026, 3, 2), 120_000),
        (date(2026, 3, 2), 120_000),
        (date(2026, 5, 31), -2_000),
    ]
    assert len({t.id for t in lot}) == 3
    assert all(t.compte_bancaire == "67499359" for t in lot)


def _bq(id_: str, jour: date, compte: str) -> Ecriture:
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.BQ,
        date=jour,
        libelle="x",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte, Sens.DEBIT, Money(100)),
            LigneEcriture("706", Sens.CREDIT, Money(100)),
        ),
    )


def test_seules_les_operations_digifactory_du_compte_fixent_la_limite() -> None:
    compte = CompteBancaire(D, "67499359", "5121", "Bred", retenu=True)
    ecritures = [
        _bq(f"{D}:releve-a", date(2026, 3, 1), "5121"),
        _bq(f"{D}:digifactory-b", date(2026, 7, 1), "5122"),
        _bq(f"{D}:digifactory-c", date(2026, 6, 1), "5121"),
    ]
    assert premiere_operation_digifactory(ecritures, D, compte) == date(2026, 6, 1)
