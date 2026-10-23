"""Teste la démo sur un vrai dossier complet (doc 17 §2, reformulé par
Louis le 2026-09-05 : « ressembler à un produit », pas un exemple à 2-3
lignes). Contrairement à tests/test_demo.py (fixtures synthétiques), ceci
tourne sur les 543 transactions réelles d'un vrai dossier — skip gracieux
si le CSV audit n'est pas présent sur ce poste (gitignored).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from axelcompta.demo_dossier_reel import (
    ANNEE_PAR_DEFAUT,
    DOSSIER_PAR_DEFAUT,
    construire_liasse,
    executer,
    executer_cerfa_2065,
    executer_exports_comptables,
)
from axelcompta.ingestion.providers.file_import import CSV_AUDIT_PAR_DEFAUT

pytestmark = pytest.mark.skipif(
    not CSV_AUDIT_PAR_DEFAUT.is_file(),
    reason="CSV audit non présent sur ce poste (gitignored, _AUDIT_DONNEES/resultats/)",
)


def test_construire_liasse_sur_un_dossier_reel_complet() -> None:
    liasse = construire_liasse()
    assert liasse.dossier_id == DOSSIER_PAR_DEFAUT
    assert liasse.exercice == str(ANNEE_PAR_DEFAUT)
    # Un vrai dossier a un vrai chiffre d'affaires et de vraies charges, pas
    # juste 2-3 lignes — sinon le fix "recettes_plateformes -> 706" aurait
    # un chiffre d'affaires resté à zéro sans qu'on s'en aperçoive.
    assert liasse.cases["CA_HT"] > 20_000_00
    assert liasse.cases["CHARGES"] > 20_000_00
    assert abs(liasse.cases["RESULTAT"]) < liasse.cases["CA_HT"]  # pas un résultat aberrant
    assert liasse.cases["RESULTAT"] == liasse.cases["CA_HT"] - liasse.cases["CHARGES"]
    # Aucune TVA plateforme ici (pas de settlement Rollee historique).
    assert liasse.cases["TVA_A_PAYER"] == 0
    # Le vrai dossier a du capital et des immobilisations : la trésorerie
    # n'égale pas le résultat, mais le bilan ventilé reste équilibré.
    assert liasse.cases["TRESORERIE"] != liasse.cases["RESULTAT"]
    assert (
        liasse.cases["TRESORERIE"]
        + liasse.cases["IMMOBILISATIONS"]
        + liasse.cases["COMPTES_NON_VENTILES"]
        == liasse.cases["RESULTAT"] + liasse.cases["TVA_A_PAYER"] + liasse.cases["CAPITAUX"]
    )
    # Ce dossier a un exercice civil complet réel (vérifié : 2024-01-01 à
    # 2024-12-31) — dérivé des vraies dates d'écriture, pas supposé.
    assert liasse.exercice_debut == date(2024, 1, 1)
    assert liasse.exercice_fin == date(2024, 12, 31)


def test_executer_produit_un_pdf_valide(tmp_path: Path) -> None:
    destination = tmp_path / "liasse.pdf"
    resultat = executer(destination)
    assert resultat == destination
    assert destination.read_bytes().startswith(b"%PDF-")


def test_executer_cerfa_2065_remplit_la_case_deficit(tmp_path: Path) -> None:
    # Ce dossier a un résultat négatif : golden test complémentaire de
    # tests/filings/test_cerfa_2065.py, sur de vraies données cette fois.
    destination = tmp_path / "cerfa.pdf"
    resultat = executer_cerfa_2065(destination)
    assert resultat == destination
    assert destination.read_bytes().startswith(b"%PDF-")


def test_executer_exports_comptables_sur_dossier_reel(tmp_path: Path) -> None:
    chemin_fec, chemin_gl, chemin_balance = executer_exports_comptables(dossier_sortie=tmp_path)
    fec = chemin_fec.read_text(encoding="utf-8")
    assert fec.startswith("JournalCode\t")
    assert fec.count("\n") > 500  # 543 transactions réelles, pas 2-3 lignes
    assert "compte,libelle_compte" in chemin_gl.read_text(encoding="utf-8")
    assert chemin_balance.is_file()
