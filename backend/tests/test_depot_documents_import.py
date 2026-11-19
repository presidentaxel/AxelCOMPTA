"""AXE-970 : ce qui entre sur une fiche quand on y dépose des fichiers."""

from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from datetime import UTC, datetime

from axelcompta.core.ids import TenantId
from axelcompta.depot_documents_import import (
    Fichier,
    depot_sur_emplacement,
    depot_sur_exercice,
    sans_doublons,
)
from axelcompta.tenants.fiches_import import nouvelle_fiche

LE = datetime(2026, 11, 17, tzinfo=UTC)
FICHE = replace(
    nouvelle_fiche("f1", TenantId("T1"), "Konate", "Kerfala", "908771033", "a@x.fr", LE),
    champs={"siren": "908771033", "cloture": "30/09", "date_creation": "2022-01-03"},
)
FEC = (
    b"JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tPieceRef\tEcritureLib"
    b"\tDebit\tCredit\tValidDate\r\n"
    b"BQ\t1\t20220105\t5120010\tP1\tApport\t1000,00\t0,00\t20220105\r\n"
    b"BQ\t1\t20220105\t1013100\tP1\tApport\t0,00\t1000,00\t20220105\r\n"
)


def _zip(fichiers: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        for nom, contenu in fichiers.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


def test_un_depot_en_vrac_range_chaque_fichier_dans_son_exercice() -> None:
    fichiers = [
        Fichier("Balance Comptable.pdf", "application/pdf", b"%PDF"),
        Fichier("Kbis.pdf", "application/pdf", b"%PDF"),
        Fichier("KERFICE SERVICE - 2022.pdf", "application/pdf", b"%PDF"),
    ]
    lot = depot_sur_exercice(FICHE, 2022, fichiers, "a@x.fr", LE)
    assert [d.emplacement for d, _ in lot] == [
        "reprise:balance:2022",
        "documents:kbis",  # permanent : sans exercice
        "reprise:autre:2022",  # rien ne parle : reste dans l'exercice
    ]


def test_une_archive_reste_intacte_et_ses_fichiers_en_sortent() -> None:
    archive = _zip({"archive.zip": _zip({"90877103300010FEC20220930.csv": FEC})})
    lot = depot_sur_exercice(
        FICHE, 2022, [Fichier("archive_2022.zip", "application/zip", archive)], "a@x.fr", LE
    )
    (zip_, contenu_zip), (fec, contenu_fec) = lot
    assert (zip_.categorie, zip_.statut_traitement, contenu_zip) == ("archive", "traite", archive)
    assert fec.origine_id == zip_.id
    assert fec.emplacement == "reprise:fec:2022"
    assert fec.nom_fichier == "archive_2022.zip/archive.zip/90877103300010FEC20220930.csv"
    assert fec.statut_traitement == "traite" and fec.donnees is not None
    assert fec.donnees["soldes_cts"] == {"1013100": -100000, "5120010": 100000}
    assert contenu_fec == FEC


def test_une_archive_sans_exercice_prend_l_annee_du_fec() -> None:
    archive = _zip({"90877103300010FEC20220930.csv": FEC, "notes.txt": b"x"})
    lot = depot_sur_emplacement(
        FICHE, "documents:autre", Fichier("vieux.zip", "", archive), "a@x.fr", LE
    )
    assert [d.emplacement for d, _ in lot] == [
        "documents:autre",
        "reprise:fec:2022",
        "documents:autre",
    ]


def test_une_archive_abimee_est_gardee_et_dite_illisible() -> None:
    (seul,) = depot_sur_emplacement(
        FICHE, "reprise:archive:2022", Fichier("a.zip", "", b"PK\x03\x04abime"), "a@x.fr", LE
    )
    assert seul[0].statut_traitement == "illisible"
    assert seul[0].resume.startswith("Archive : archive zip illisible")


def test_un_contenu_deja_sur_la_fiche_n_est_pas_redepose() -> None:
    """AXE-971 : l'archive déposée par-dessus des fichiers déjà là n'ajoute
    que ce qui manque ; une archive déjà déposée est écartée en entier."""
    grand_livre = b"%PDF grand livre"
    archive = _zip({"Grand Livre.pdf": grand_livre, "90877103300010FEC20220930.csv": FEC})
    seul = depot_sur_exercice(
        FICHE, 2022, [Fichier("Grand Livre.pdf", "", grand_livre)], "a@x.fr", LE
    )
    deja = {d.empreinte for d, _ in seul}

    lot = depot_sur_exercice(FICHE, 2022, [Fichier("a.zip", "", archive)], "a@x.fr", LE)
    gardes, ecartes = sans_doublons(lot, deja)
    assert [d.categorie for d, _ in gardes] == ["archive", "fec"]
    assert ecartes == ["Grand Livre.pdf"]
    assert gardes[0][0].resume == (
        "Archive gardée intacte : 1 fichier(s) rangé(s) à part, 1 déjà sur la fiche."
    )

    deja |= {d.empreinte for d, _ in gardes}
    encore = depot_sur_exercice(FICHE, 2022, [Fichier("a.zip", "", archive)], "a@x.fr", LE)
    assert sans_doublons(encore, deja) == ([], ["a.zip"])


def test_un_meme_fichier_depose_deux_fois_d_un_coup_ne_compte_qu_une_fois() -> None:
    double = [Fichier("x.pdf", "", b"%PDF x"), Fichier("copie de x.pdf", "", b"%PDF x")]
    gardes, ecartes = sans_doublons(depot_sur_exercice(FICHE, 2022, double, "a", LE), set())
    assert [d.nom_fichier for d, _ in gardes] == ["x.pdf"]
    assert ecartes == ["copie de x.pdf"]


def test_un_telechargement_interrompu_est_dit_incomplet_meme_dans_une_archive() -> None:
    """AXE-1001 : « Balance Comptable LSKN COMPAGNY.pdf.crdownload » (Chrome)
    ne se lit pas : il se redemande, et la fiche ne peut pas être traitée."""
    archive = _zip({"Clôture 2023-2024/Balance Comptable.pdf.crdownload": b"%PDF-1.4 tronq"})
    lot = depot_sur_exercice(
        FICHE, 2024, [Fichier("Clôture 2023-2024.zip", "application/zip", archive)], "a@x.fr", LE
    )
    (_zip_, _), (incomplet, _) = lot
    assert incomplet.statut_traitement == "illisible"
    assert incomplet.resume == (
        "Téléchargement incomplet (.crdownload) : redemandez ce fichier au client."
    )


def test_un_tableur_est_a_lire_a_la_main_et_un_pdf_par_l_ocr() -> None:
    """AXE-1001 : l'OCR ne lit que les PDF et les images ; l'écran le dit dès le dépôt."""
    tableur = b"PK\x03\x04 xl/workbook.xml"
    ((excel, _),) = depot_sur_emplacement(
        FICHE, "reprise:autre:2025", Fichier("CA 2025.xlsx", "", tableur), "a@x.fr", LE
    )
    ((pdf, _),) = depot_sur_emplacement(
        FICHE, "reprise:liasse:2025", Fichier("liasse.pdf", "", b"%PDF-1.4"), "a@x.fr", LE
    )
    assert (excel.statut_traitement, excel.resume) == (
        "a_traiter",
        "À lire à la main : l'OCR ne lit que les PDF et les images.",
    )
    assert pdf.resume.startswith("À lire : sera lu par l'OCR")
