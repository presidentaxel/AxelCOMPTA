from __future__ import annotations

import io

from pypdf import PdfReader

from axelcompta.filings.cerfa_2065 import CHEMIN_FORMULAIRE_OFFICIEL
from axelcompta.filings.overlay_cerfa import OverlayCerfa, formater_date, formater_euros, texte_case


def test_format_des_montants_de_la_liasse() -> None:
    assert formater_euros(14_191) == "14 191"
    assert formater_euros(-1_346) == "-1 346"
    assert formater_euros(0) == "0"


def test_une_case_a_zero_reste_vide() -> None:
    assert texte_case(0) is None
    assert texte_case(1_346) == "1 346"
    assert formater_date(31, 12, 2025) == "31122025"


def test_ecrit_sur_la_page_demandee_sans_toucher_aux_autres() -> None:
    overlay = OverlayCerfa(CHEMIN_FORMULAIRE_OFFICIEL)
    overlay.texte(2, 100.0, 100.0, "MARQUEUR-PAGE-2")
    overlay.montant(1, (0.0, 300.0, 300.0), 1_234_567)
    lecteur = PdfReader(io.BytesIO(overlay.rendre()))
    assert "MARQUEUR-PAGE-2" in (lecteur.pages[1].extract_text() or "")
    assert "MARQUEUR-PAGE-2" not in (lecteur.pages[0].extract_text() or "")
    assert "1 234 567" in (lecteur.pages[0].extract_text() or "")
