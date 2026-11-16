"""Origines CORS : le poste de dev, plus l'adresse publique en production."""

from __future__ import annotations

from axelcompta.api.origines import origines_autorisees

_DEV = ["http://localhost:3000", "http://localhost:3001"]


def test_le_poste_de_dev_reste_autorise() -> None:
    assert origines_autorisees({}) == _DEV


def test_l_adresse_publique_est_ajoutee_sans_chemin() -> None:
    origines = origines_autorisees(
        {"AXELCOMPTA_URL_APP": "https://App.Exemple.fr/portefeuille/", "AXELCOMPTA_ORIGINES": ""}
    )
    assert origines == [*_DEV, "https://app.exemple.fr"]


def test_les_origines_supplementaires_ignorent_ce_qui_n_est_pas_une_origine() -> None:
    origines = origines_autorisees(
        {
            "AXELCOMPTA_URL_APP": "http://localhost:3000",
            "AXELCOMPTA_ORIGINES": (
                " https://api.exemple.fr , javascript:alert(1), https://user:mdp@app.exemple.fr, *"
            ),
        }
    )
    assert origines == [*_DEV, "https://api.exemple.fr"]


def test_une_adresse_ipv6_garde_ses_crochets() -> None:
    origines = origines_autorisees({"AXELCOMPTA_URL_APP": "https://[::1]:8443"})
    assert "https://[::1]:8443" in origines
