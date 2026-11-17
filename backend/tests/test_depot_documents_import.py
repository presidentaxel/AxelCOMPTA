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
