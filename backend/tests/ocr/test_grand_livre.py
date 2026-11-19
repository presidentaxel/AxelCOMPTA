"""AXE-999 : un grand livre ne coûte plus que ses dernières pages, et rien
quand le FEC du même exercice est lu."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import UTC, datetime

from pypdf import PdfReader, PdfWriter

from axelcompta.core.ids import TenantId
from axelcompta.ocr.categories import Categorie
from axelcompta.ocr.lecture import Appel
from axelcompta.ocr.pages import dernieres_pages
from axelcompta.ocr.passage import SANS_LECTURE, a_lire, passer
from axelcompta.tenants.fiches_import import document_import, nouvelle_fiche
from axelcompta.tenants.fiches_import_depot import FichesImportMemoire

T = TenantId("T")
LE = datetime(2026, 11, 19, tzinfo=UTC)
GL_LU: dict[str, object] = {
    "siren": "",
    "exercice_debut": "2023-10-01",
    "exercice_fin": "2024-09-30",
    "montants": [
        {"nom": "total_debit_cts", "valeur_cts": 1234500},
        {"nom": "total_credit_cts", "valeur_cts": 1234500},
    ],
}


def _pdf(pages: int) -> bytes:
    ecrivain = PdfWriter()
    for _ in range(pages):
        ecrivain.add_blank_page(width=200, height=200)
    sortie = io.BytesIO()
    ecrivain.write(sortie)
    return sortie.getvalue()


def _pages(contenu: bytes) -> int:
    return len(PdfReader(io.BytesIO(contenu)).pages)


def test_un_pdf_est_reduit_a_ses_dernieres_pages() -> None:
    assert _pages(dernieres_pages(_pdf(30), 2)) == 2
    court = _pdf(2)
    assert dernieres_pages(court, 2) == court
    assert dernieres_pages(b"%PDF-1.4 abime", 2) == b"%PDF-1.4 abime"


class Appels:
    def __init__(self) -> None:
        self.pages: list[int] = []

    def __call__(self, _m: str, _c: Categorie, contenu: bytes, _media: str) -> Appel:
        self.pages.append(_pages(contenu))
        return Appel(GL_LU, 0.002)


def _fiche(avec_fec: bool) -> tuple[FichesImportMemoire, str]:
    fiches = FichesImportMemoire()
    fiche = nouvelle_fiche("f", T, "Kerfice", "K", "908771033", "b", LE)
    fiches.enregistrer(fiche)
    contenu = _pdf(40)
    gl = document_import("gl", fiche, "reprise:grand_livre:2024", "GL.pdf", "", contenu, "b", LE)
    fiches.deposer(gl, contenu)
    if avec_fec:
        fec = document_import("fec", fiche, "reprise:fec:2024", "FEC.txt", "", b"fec", "b", LE)
        lu = {"type": "fec", "resultat_cts": 100, "soldes_cts": {}}
        fiches.deposer(replace(fec, statut_traitement="traite", donnees=lu), b"fec")
    return fiches, fiche.id


def test_un_grand_livre_sans_fec_n_envoie_que_ses_deux_dernieres_pages() -> None:
    fiches, fiche_id = _fiche(avec_fec=False)
    appels = Appels()
    passer(fiches, T, appels, LE, plafond_usd=5.0)
    gl = next(d for d in fiches.instantane(T, fiche_id).documents if d.id == "gl")
    assert appels.pages == [2]
    assert gl.statut_traitement == "traite"


def test_un_grand_livre_dont_le_fec_est_lu_n_est_pas_envoye() -> None:
    fiches, fiche_id = _fiche(avec_fec=True)
    appels = Appels()
    bilan = passer(fiches, T, appels, LE, plafond_usd=5.0)
    gl = next(d for d in fiches.instantane(T, fiche_id).documents if d.id == "gl")
    assert appels.pages == []
    assert (gl.statut_traitement, gl.resume) == ("traite", SANS_LECTURE)
    assert bilan.cout_usd == 0.0
    assert not a_lire(gl)
