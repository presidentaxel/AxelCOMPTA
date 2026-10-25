from __future__ import annotations

import csv
import io
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.filings.export_comptable import exporter_balance, exporter_grand_livre
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

DOSSIER = DossierId("d1")


def _ecriture_uber() -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 9, 3),
        libelle="Règlement Uber",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(848_00)),
            LigneEcriture("706", Sens.CREDIT, Money(945_45)),
            LigneEcriture("44571", Sens.CREDIT, Money(94_55)),
            LigneEcriture("622", Sens.DEBIT, Money(160_00)),
            LigneEcriture("44566", Sens.DEBIT, Money(32_00)),
        ),
    )


def test_grand_livre_a_une_ligne_par_ligne_decriture_triee_par_compte() -> None:
    csv_texte = exporter_grand_livre((_ecriture_uber(),))
    lignes = list(csv.DictReader(io.StringIO(csv_texte)))
    assert len(lignes) == 5
    comptes = [ligne["compte"] for ligne in lignes]
    assert comptes == sorted(comptes)
    ligne_512 = next(ligne for ligne in lignes if ligne["compte"] == "512")
    assert ligne_512["montant"] == "848.00"
    assert ligne_512["sens"] == "DEBIT"
    assert ligne_512["libelle_compte"] == "Banques"


def test_balance_calcule_le_solde_debit_moins_credit() -> None:
    csv_texte = exporter_balance((_ecriture_uber(),))
    lignes = {ligne["compte"]: ligne for ligne in csv.DictReader(io.StringIO(csv_texte))}

    assert lignes["512"]["debit"] == "848.00"
    assert lignes["512"]["credit"] == ""
    assert lignes["512"]["solde"] == "848.00"

    assert lignes["706"]["credit"] == "945.45"
    assert lignes["706"]["solde"] == "-945.45"

    # équilibre global : la somme de tous les soldes vaut 0 (doc 06 §1)
    total = sum(float(ligne["solde"]) for ligne in lignes.values())
    assert round(total, 2) == 0.0


def test_une_ligne_de_balance_a_zero_sort_vide() -> None:
    aller = Ecriture(
        id=EcritureId("a"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 9, 3),
        libelle="Aller",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.DEBIT, Money(100_00)),
            LigneEcriture("471", Sens.CREDIT, Money(100_00)),
        ),
    )
    retour = Ecriture(
        id=EcritureId("b"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 9, 4),
        libelle="Retour",
        reference_piece=None,
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(100_00)),
            LigneEcriture("512", Sens.CREDIT, Money(100_00)),
        ),
    )
    lignes = {
        ligne["compte"]: ligne
        for ligne in csv.DictReader(io.StringIO(exporter_balance((aller, retour))))
    }
    assert lignes["471"]["debit"] == "100.00"
    assert lignes["471"]["credit"] == "100.00"
    assert lignes["471"]["solde"] == ""
