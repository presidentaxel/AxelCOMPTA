"""AXE-947 : les FEC et les relevés QIF déposés sur une fiche se lisent seuls.
AXE-970 : un fichier déposé en vrac se classe seul, une archive se déplie."""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from axelcompta.traitement_documents_import import (
    MEMBRES_MAX,
    ArchiveIllisible,
    QifIllisible,
    annee_du_nom,
    classer,
    deplier,
    est_fec,
    lire_qif,
    traiter,
)

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


def _zip(fichiers: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        for nom, contenu in fichiers.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


def _zip_oneup(nom: str, contenu: bytes) -> bytes:
    """Comme OneUp : un nom en UTF-8, sans le drapeau UTF-8 du zip. On écrit
    un nom ASCII de même longueur, puis on remplace ses octets."""
    brut = nom.encode("utf-8")
    ascii_ = bytes(b if b < 128 else ord("X") for b in brut)
    return _zip({ascii_.decode(): contenu}).replace(ascii_, brut)


def test_un_fec_est_lu_et_resume() -> None:
    lu = traiter("fec", "552100554FEC20251231.txt", FEC)
    assert lu.statut == "traite"
    assert lu.resume == (
        "FEC lu : 2 lignes du 02/01/2025 au 31/12/2025, équilibré, résultat 0,00 €. "
        "Clos le 31/12/2025."
    )
    assert lu.exercice == 2025
    assert lu.donnees is not None
    assert lu.donnees["siren"] == "552100554"
    assert lu.donnees["soldes_cts"] == {"101": -1050, "512": 1050}


def test_un_fec_au_siret_et_en_csv_est_reconnu_a_son_contenu() -> None:
    """OneUp : `90877103300010FEC20220930.csv`, rangé n'importe où."""
    lu = traiter("autre", "90877103300010FEC20251231.csv", FEC, siren="552100554")
    assert lu.statut == "traite" and lu.donnees is not None
    assert lu.donnees["siren"] == "908771033"
    assert "⚠ SIREN 908771033" in lu.resume


def test_un_fec_illisible_dit_pourquoi() -> None:
    lu = traiter("fec", "fec.txt", b"JournalCode\tDebit\r\n")
    assert lu.statut == "illisible" and "En-tête FEC incomplet" in lu.resume


def test_un_releve_qif_est_lu() -> None:
    operations = lire_qif(QIF)
    assert [(o.jour, o.montant_cts, o.libelle) for o in operations] == [
        (date(2026, 1, 31), -125050, "TOTAL ENERGIES"),
        (date(2026, 2, 2), 200000, "UBER Semaine 5"),
    ]
    lu = traiter("releve_bancaire", "releve.qif", QIF)
    assert lu.statut == "traite"
    assert lu.resume.startswith("QIF lu : 2 opérations du 31/01/2026 au 02/02/2026")


def test_un_qif_americain_et_un_faux_qif() -> None:
    (operation,) = lire_qif(b"!Type:Bank\nD12/31'25\nT-3.68\nPAdjust\n^\n")
    assert operation.jour == date(2025, 12, 31)
    with pytest.raises(QifIllisible, match="pas un fichier QIF"):
        lire_qif(b"Date;Montant\n")
    assert traiter("releve_bancaire", "releve.qif", b"rien").statut == "illisible"


def test_un_pdf_reste_a_lire() -> None:
    lu = traiter("liasse", "liasse.pdf", b"%PDF-1.4")
    assert lu.statut == "a_traiter" and "OCR" in lu.resume


@pytest.mark.parametrize(
    ("nom", "categorie"),
    [
        ("Balance Comptable KERFICE SERVICE.pdf", "balance"),
        ("Grand Livre KERFICE SERVICE.pdf", "grand_livre"),
        ("Synthèse de la déclaration tva.pdf", "declaration_tva"),
        ("Synthèse de la déclaration IS.pdf", "declaration_is"),
        ("Accusé de réception de la déclaration IS.pdf", "accuse_reception"),
        ("paiement_IS_20230119_120935.pdf", "paiement_impot"),
        ("Bilan Comptable.pdf", "comptes_annuels"),
        ("Compte de Résultat.pdf", "comptes_annuels"),
        ("Encaissements de Vente/ENC-117/ENC-117.pdf", "piece"),
        ("liasse 2033 2024.pdf", "liasse"),
        ("Kbis.pdf", "kbis"),
        ("KERFICE SERVICE - 2022.pdf", "autre"),
    ],
)
def test_un_fichier_se_classe_a_son_nom(nom: str, categorie: str) -> None:
    assert classer(nom, b"%PDF-1.4") == categorie


def test_le_contenu_l_emporte_sur_le_nom() -> None:
    assert classer("export.csv", FEC) == "fec"
    assert classer("rien.bin", _zip({"a.txt": b"a"})) == "archive"
    # L'impression PDF d'un FEC n'est pas un FEC.
    assert classer("908771033FEC20221231.pdf", b"%PDF-1.4") == "autre"
    assert est_fec(b"\xef\xbb\xbfJournalCode|JournalLib")


def test_l_annee_se_lit_dans_le_nom() -> None:
    assert annee_du_nom("90877103300010FEC20220930.csv") == 2022
    assert annee_du_nom("liasse 2019.pdf", {2019, 2020}) == 2019
    assert annee_du_nom("liasse 2019.pdf", {2020}) is None
    assert annee_du_nom("bilan.pdf") is None


def test_une_archive_imbriquee_se_deplie_sans_sa_signature() -> None:
    """L'archive fiscale OneUp : un zip signé qui contient un autre zip, avec
    des noms en UTF-8 sans le drapeau."""
    interieur = _zip_oneup("Compte de Résultat.pdf", b"%PDF")
    archive = _zip(
        {
            "archive.zip": interieur,
            "FEC.csv": FEC,
            "META-INF/signature.pkcs7": b"sig",
            "mimetype.txt": b"application/zip",
            "__MACOSX/._x": b"",
        }
    )
    membres = deplier(archive)
    assert [m.chemin for m in membres] == ["archive.zip/Compte de Résultat.pdf", "FEC.csv"]
    assert membres[1].contenu == FEC


def test_une_archive_abimee_ou_trop_grosse_est_refusee() -> None:
    with pytest.raises(ArchiveIllisible, match="illisible"):
        deplier(b"PK\x03\x04pas un zip")
    trop = _zip({f"f{i}.txt": b"" for i in range(MEMBRES_MAX + 1)})
    with pytest.raises(ArchiveIllisible, match="trop grosse"):
        deplier(trop)


def test_les_fichiers_techniques_oneup_restent_dans_l_archive() -> None:
    """AXE-972 : `info.txt` et `logs.txt` de l'archive fiscale OneUp ne
    sortent pas ; un `info.txt` ordinaire, si."""
    archive = _zip(
        {
            "archive.zip": _zip(
                {
                    "info.txt": b"Software\tOneUp\nGenerated at\t2023",
                    "logs.txt": b'"JETNID","JETEVTNUM","JETEVTLIB"\n',
                    "Grand Livre.pdf": b"%PDF gl",
                }
            ),
            "notes/info.txt": b"Rappeler le comptable",
        }
    )
    assert [m.chemin for m in deplier(archive)] == ["archive.zip/Grand Livre.pdf", "notes/info.txt"]


def test_l_impression_du_fec_va_avec_le_fec_sans_se_lire() -> None:
    nom = "archive.zip/FEC - Fichier à plat CSV.pdf"
    assert classer(nom, b"%PDF-1.4") == "fec"
    lu = traiter("fec", nom, b"%PDF-1.4")
    assert lu.statut == "a_traiter" and lu.resume.startswith("Impression PDF du FEC")
    # Un dossier nommé FEC ne fait pas de ses PDF des impressions.
    assert classer("FEC/Balance.pdf", b"%PDF-1.4") == "balance"


def test_la_synthese_de_la_declaration_de_resultat_est_la_liasse() -> None:
    assert classer("Synthèse de la déclaration RESULTAT.pdf", b"%PDF") == "liasse"
    assert classer("Accusé de réception de la déclaration RESULTAT.pdf", b"%PDF") == (
        "accuse_reception"
    )


def _pdf(lignes: list[str]) -> bytes:
    import io

    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    page = canvas.Canvas(tampon)
    for rang, ligne in enumerate(lignes):
        page.drawString(40, 800 - 14 * rang, ligne)
    page.save()
    return tampon.getvalue()


RECAP_UBER = [
    "Uber B.V.",
    "SIREN/SIRET: 123456789",
    "01-31 Octobre 2025",
    "Récapitulatif fiscal",
    "Revenus issus de courses 2 000,00 €",
    "Revenus issus d'autres services 50,00 €",
    "Frais de service Uber 600,00 €",
    "Montant total 1 450,00 €",
]


def test_un_recapitulatif_uber_est_range_et_lu() -> None:
    """AXE-987 : rangé en récapitulatif de plateforme, lu sans OCR."""
    contenu = _pdf(RECAP_UBER)
    assert classer("uber_monthly_2025_10.pdf", contenu) == "releve_plateforme"
    lu = traiter("releve_plateforme", "uber_monthly_2025_10.pdf", contenu)
    assert lu.statut == "traite"
    assert lu.resume.startswith("Récapitulatif Uber d'octobre 2025 : courses 2 000,00 €")
    assert lu.donnees is not None and lu.donnees["mois"] == "2025-10"
    assert lu.exercice == 2025


def test_un_pdf_de_plateforme_inconnu_reste_a_lire() -> None:
    lu = traiter("releve_plateforme", "bolt.pdf", _pdf(["Bolt Operations", "Weekly report"]))
    assert lu.statut == "a_traiter"


def test_un_classeur_excel_dans_une_archive_reste_un_fichier() -> None:
    """AXE-988 : un .xlsx est un zip, mais un seul fichier."""
    classeur = _zip({"[Content_Types].xml": b"<x/>", "xl/workbook.xml": b"<w/>"})
    membres = deplier(_zip({"RECAPS/CA 2025.xlsx": classeur, "RECAPS/a.pdf": b"%PDF"}))
    assert sorted(m.chemin for m in membres) == ["RECAPS/CA 2025.xlsx", "RECAPS/a.pdf"]
    assert classer("CA 2025.xlsx", classeur) == "autre"
    assert classer("rien.bin", _zip({"a.txt": b"a"})) == "archive"


def test_un_releve_societe_generale_du_mois_est_un_releve_bancaire() -> None:
    assert classer("RC/SG 10-2025.pdf", b"%PDF") == "releve_bancaire"
    assert classer("Relevé Societe Generale.pdf", b"%PDF") == "releve_bancaire"
    assert classer("RC/SG TARIFS.pdf", b"%PDF") == "autre"


def test_un_tableau_d_amortissement_est_un_emprunt() -> None:
    assert classer("Tableau d'amortissement prêt Bred.pdf", b"%PDF") == "emprunt"
    assert classer("echeancier_credit.pdf", b"%PDF") == "emprunt"
