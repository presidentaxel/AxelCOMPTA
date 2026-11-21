from __future__ import annotations

import dataclasses
import io
from datetime import date

import pytest
from pypdf import PdfReader

from axelcompta.closing.bilan_simplifie import ClotureSimplifieeService
from axelcompta.closing.immobilisations import Cession, Immobilisation
from axelcompta.closing.models import LiassePivot
from axelcompta.core.ids import DossierId
from axelcompta.demo_chauffeurs_type import construire_ledger, parametres_cloture
from axelcompta.filings.cerfa_2050 import PAGES, PdfLiasse2050Renderer, cellule_2059a
from axelcompta.filings.liasse_fiscale import PdfLiasseFiscaleRenderer
from axelcompta.ingestion.providers.chauffeurs_demo import PROFIL_KARIM

# Cases de la liasse pivot qui n'ont pas de place sur le formulaire 2026.
SANS_CASE = {"2058B.K4bis"}  # toujours 0 : aucun déficit transféré


def _liasse_reelle() -> LiassePivot:
    vehicule = Immobilisation(
        "v1",
        "Toyota",
        "2182",
        date(2023, 1, 1),
        30_000_00,
        60,
        cession=Cession(date(2025, 12, 1), 12_000_00),
    )
    ledger, _ = construire_ledger(PROFIL_KARIM)
    parametres = dataclasses.replace(
        parametres_cloture(PROFIL_KARIM), regime_liasse="2050", immobilisations=(vehicule,)
    )
    return ClotureSimplifieeService(ledger).cloturer(PROFIL_KARIM.dossier_id, "2025", parametres)


def test_toutes_les_cases_calculees_existent_sur_le_formulaire() -> None:
    # Une case calculée sans coordonnée serait silencieusement absente du PDF.
    renderer = PdfLiasse2050Renderer()
    for cle in _liasse_reelle().cases:
        tableau, _, code = cle.partition(".")
        if cle in SANS_CASE:
            continue
        if tableau == "2059A":
            ligne, _, colonne = code.partition(".C")
            if ligne != "TOTAL":  # les totaux 2 à 8 n'ont pas de case
                assert cellule_2059a(code) is not None, cle
        elif tableau in PAGES:
            assert renderer.cellule(PAGES[tableau], code.removesuffix(".1AN")), cle


def test_le_bilan_et_la_plus_value_sont_ecrits() -> None:
    liasse = _liasse_reelle()
    pdf = PdfLiasse2050Renderer().rendre(liasse)
    pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages]
    assert len(pages) == 19
    total = f"{liasse.cases['2050.EE'] // 100:,}".replace(",", " ")
    assert total in pages[1]  # total du passif, 2051
    assert "AMRANI VTC" in pages[0] and "AMRANI VTC" in pages[8]
    assert "12 000" in pages[12]  # prix de vente au 2059-A


def test_la_liasse_complete_sert_le_2050_au_reel_normal() -> None:
    pdf = PdfLiasseFiscaleRenderer().rendre(_liasse_reelle())
    textes = [page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages]
    assert any("2050-SD" in texte for texte in textes)
    assert not any("2033-A-SD" in texte for texte in textes)


def test_refuse_une_liasse_sans_cases_2050() -> None:
    with pytest.raises(ValueError):
        PdfLiasse2050Renderer().rendre(LiassePivot(DossierId("d"), "2025", {"2065": 0}))
