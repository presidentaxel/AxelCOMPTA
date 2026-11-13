"""AXE-871 : un seuil par catégorie, au-dessus duquel le modèle ne s'est jamais trompé."""

from __future__ import annotations

from axelcompta.categorize.seuils import seuils_sans_erreur


def _vues(categorie: str, confiances: list[float], juste: bool) -> list[tuple[str, float, bool]]:
    return [(categorie, c, juste) for c in confiances]


def test_le_seuil_s_arrete_sous_la_premiere_erreur() -> None:
    observations = _vues("carburant", [0.99, 0.97, 0.95, 0.93], True) + _vues(
        "carburant", [0.9], False
    )
    assert seuils_sans_erreur(observations, minimum=3) == {"carburant": 0.93}


def test_pas_assez_d_observations_pas_de_seuil() -> None:
    assert seuils_sans_erreur(_vues("peage", [0.99, 0.98], True), minimum=3) == {"peage": None}


def test_une_erreur_tout_en_haut_interdit_l_imputation() -> None:
    observations = _vues("repas", [0.99], False) + _vues("repas", [0.9, 0.8, 0.7], True)
    assert seuils_sans_erreur(observations, minimum=1) == {"repas": None}


def test_une_erreur_a_egalite_avec_le_seuil_le_rend_faux() -> None:
    observations = _vues("x", [0.9, 0.8], True) + _vues("x", [0.8], False)
    seuil = seuils_sans_erreur(observations, minimum=1)["x"]
    assert seuil is None or seuil > 0.8


def test_les_categories_sont_independantes() -> None:
    observations = _vues("a", [0.9] * 3, True) + _vues("b", [0.95], False)
    assert seuils_sans_erreur(observations, minimum=3) == {"a": 0.9, "b": None}
