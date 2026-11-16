"""AXE-947 : les FEC et les relevés QIF déposés sur une fiche se lisent seuls."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.traitement_documents_import import QifIllisible, lire_qif, traiter

FEC = (
    b"JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tPieceRef\tEcritureLib\tMontant\tSens\tValidDate\r\n"
    b"OD\t1\t20250102\t512\tP\tL\t10.5\tD\t20250102\r\n"
    b"OD\t1\t20251231\t101\tP\tL\t10,50\tC\t20251231\r\n"
)
QIF = (
    b"!Type:Bank\n"
    b"D31/01/2026\nT-1 250,50\nPTOTAL ENERGIES\n^\n"
    b"D02/02/2026\nT2000.00\nPUBER\nMSemaine 5\n^\n"
)


def test_un_fec_est_lu_et_resume() -> None:
    statut, resume = traiter("fec", "552100554FEC20251231.txt", FEC)
    assert statut == "traite"
    assert resume == "FEC lu : 2 lignes du 02/01/2025 au 31/12/2025, équilibré."


def test_un_fec_illisible_dit_pourquoi() -> None:
    statut, resume = traiter("fec", "fec.txt", b"JournalCode\tDebit\r\n")
    assert statut == "illisible" and "En-tête FEC incomplet" in resume


def test_un_releve_qif_est_lu() -> None:
    operations = lire_qif(QIF)
    assert [(o.jour, o.montant_cts, o.libelle) for o in operations] == [
        (date(2026, 1, 31), -125050, "TOTAL ENERGIES"),
        (date(2026, 2, 2), 200000, "UBER Semaine 5"),
    ]
    statut, resume = traiter("releve_bancaire", "releve.qif", QIF)
    assert statut == "traite"
    assert resume.startswith("QIF lu : 2 opérations du 31/01/2026 au 02/02/2026")


def test_un_qif_americain_et_un_faux_qif() -> None:
    (operation,) = lire_qif(b"!Type:Bank\nD12/31'25\nT-3.68\nPAdjust\n^\n")
    assert operation.jour == date(2025, 12, 31)
    with pytest.raises(QifIllisible, match="pas un fichier QIF"):
        lire_qif(b"Date;Montant\n")
    assert traiter("releve_bancaire", "releve.qif", b"rien")[0] == "illisible"


def test_un_pdf_reste_a_lire() -> None:
    statut, resume = traiter("liasse", "liasse.pdf", b"%PDF-1.4")
    assert statut == "a_traiter" and "OCR" in resume
