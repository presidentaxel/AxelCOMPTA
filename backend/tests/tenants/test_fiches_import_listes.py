"""AXE-946 : associés et comptes Rollee d'une fiche d'import."""

from __future__ import annotations

import json

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.tenants.fiches_import_listes import (
    associes_du_registre,
    lire_associes,
    ranger_associes,
    ranger_comptes_rollee,
    total_parts,
)


def test_les_associes_sont_ranges_et_leur_total_controle() -> None:
    texte = ranger_associes(
        json.dumps(
            [
                {
                    "prenom": " Karim ",
                    "nom": "Dupont",
                    "fonction": "president",
                    "pourcentage": "60,5 %",
                },
                {"prenom": "Lina", "nom": "Dupont", "pourcentage": "39.5"},
            ]
        )
    )
    associes = lire_associes(texte)
    assert [(a.prenom, a.fonction, a.pourcentage) for a in associes] == [
        ("Karim", "president", "60.5"),
        ("Lina", "associe", "39.5"),
    ]
    assert total_parts(associes) == 100
    for lignes, message in (
        ([{"prenom": "Sans nom"}], "nom de chaque associé"),
        ([{"nom": "A", "fonction": "tresorier"}], "fonction inconnue"),
        ([{"nom": "A", "pourcentage": "120"}], "entre 0 et 100"),
        ([{"nom": "A", "pourcentage": "70"}, {"nom": "B", "pourcentage": "40"}], "dépasse 100"),
    ):
        with pytest.raises(SaisieInvalide, match=message):
            ranger_associes(json.dumps(lignes))


def test_une_ancienne_saisie_libre_se_lit_comme_une_liste_vide() -> None:
    assert lire_associes("Karim Dupont 100 %") == []
    assert lire_associes(None) == []


def test_les_dirigeants_du_registre_deviennent_des_associes_a_completer() -> None:
    lignes = json.loads(
        associes_du_registre(
            [("DUPONT", "Marie Claire", ("73",)), ("MARTIN", "Jean", ("53",))], "SARL"
        )
    )
    assert lignes == [
        {"prenom": "Marie Claire", "nom": "DUPONT", "fonction": "president", "pourcentage": ""},
        {
            "prenom": "Jean",
            "nom": "MARTIN",
            "fonction": "gerant",
            "pourcentage": "",
        },  # 53 : non deviné
    ]
    assert associes_du_registre([], "SASU") == ""


def test_les_comptes_rollee_retenus_sans_doublon() -> None:
    compte = {"rollee_user_id": "u1", "nom": "Karim Dupont", "plateformes": ["uber", 3]}
    texte = ranger_comptes_rollee(json.dumps([compte, compte]))
    assert json.loads(texte) == [
        {"rollee_user_id": "u1", "nom": "Karim Dupont", "plateformes": ["uber"]}
    ]
    with pytest.raises(SaisieInvalide, match="compte illisible"):
        ranger_comptes_rollee(json.dumps([{"nom": "sans identifiant"}]))
