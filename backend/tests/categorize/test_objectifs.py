"""AXE-816 : les objectifs V1 de la catégorisation, mesurés sur un jeu étiqueté."""

from __future__ import annotations

from axelcompta.categorize.objectifs import (
    Observation,
    mesurer,
    par_categorie,
    par_etage,
    tableau,
)

JEU = [
    *[Observation("regle", True, "carburant", "carburant")] * 6,
    Observation("regle", True, "retrait_especes", "frais_bancaires"),
    Observation("modele", False, "peage_stationnement", "repas_et_receptions"),
    Observation("aucun", False, None, "repas_et_receptions"),
    Observation("aucun", False, None, "usage_personnel"),
]


def test_les_quatre_objectifs_sont_mesures() -> None:
    auto, precision, regles, llm = mesurer(JEU)
    assert (auto.mesure, auto.atteint) == (70.0, False)
    assert precision.mesure == 85.7 and precision.atteint is False
    assert (regles.mesure, regles.atteint) == (70.0, True)
    assert (llm.mesure, llm.atteint) == (20.0, False)  # « ≤ 10 % »


def test_un_jeu_vide_ne_mesure_rien() -> None:
    assert all(o.mesure is None and o.atteint is None for o in mesurer([]))


def test_le_detail_par_etage_et_par_categorie() -> None:
    assert par_etage(JEU)["regle"] == (7, 6, 1)
    assert par_etage(JEU)["modele"] == (1, 0, 0)
    assert par_categorie(JEU)["repas_et_receptions"] == (2, 0, 0)
    assert par_categorie(JEU)["carburant"] == (6, 6, 6)


def test_le_tableau_ne_montre_aucun_libelle() -> None:
    texte = tableau(mesurer(JEU), "Test")
    assert "| Recours au LLM | ≤ 10 % | 20 % | **non** |" in texte
