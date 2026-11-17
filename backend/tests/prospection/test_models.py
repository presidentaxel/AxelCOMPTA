"""AXE-949 : la saisie du formulaire, nettoyée et vérifiée avec ses phrases."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.prospection.models import LONGUEUR_MAX, DemandeEchange, preparer_demande

MAINTENANT = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)


def _demande(**champs: str | None) -> DemandeEchange:
    base: dict[str, str | None] = {
        "nom": "Claire Martin",
        "email": "claire@cabinet-martin.fr",
        "organisation": "Cabinet Martin",
        "role": "cabinet",
        "message": None,
    }
    base.update(champs)
    return preparer_demande(
        id="d1",
        nom=base["nom"] or "",
        email=base["email"] or "",
        organisation=base["organisation"] or "",
        role=base["role"] or "",
        message=base["message"],
        cree_le=MAINTENANT,
    )


def test_une_saisie_valide_est_gardee_telle_quelle() -> None:
    demande = _demande(message="Nous suivons 40 dossiers VTC.")
    assert demande.nom == "Claire Martin"
    assert demande.role == "cabinet"
    assert demande.message == "Nous suivons 40 dossiers VTC."
    assert demande.cree_le == MAINTENANT
    assert demande.notifiee_le is None


def test_les_espaces_sont_retires_et_l_adresse_passe_en_minuscules() -> None:
    demande = _demande(nom="  Claire Martin ", email=" Claire@Cabinet-Martin.FR ")
    assert demande.nom == "Claire Martin"
    assert demande.email == "claire@cabinet-martin.fr"


def test_un_message_vide_devient_absent() -> None:
    assert _demande(message="   ").message is None


def test_les_caracteres_de_controle_sont_retires_mais_pas_les_retours_a_la_ligne() -> None:
    demande = _demande(nom="Claire\x00 Martin", message="Bonjour\x07,\nmerci.")
    assert demande.nom == "Claire Martin"
    assert demande.message == "Bonjour,\nmerci."


@pytest.mark.parametrize(
    ("champs", "phrase"),
    [
        ({"nom": "   "}, "Indiquez votre nom."),
        ({"email": ""}, "Indiquez une adresse e-mail valide."),
        ({"email": "claire@cabinet"}, "Indiquez une adresse e-mail valide."),
        ({"email": "claire martin@cabinet.fr"}, "Indiquez une adresse e-mail valide."),
        ({"organisation": ""}, "Indiquez votre organisation."),
        ({"role": "chauffeur"}, "Indiquez si vous êtes un cabinet ou une centrale."),
        ({"role": ""}, "Indiquez si vous êtes un cabinet ou une centrale."),
    ],
)
def test_une_saisie_invalide_dit_quoi_corriger(champs: dict[str, str], phrase: str) -> None:
    with pytest.raises(SaisieInvalide) as erreur:
        _demande(**champs)
    assert str(erreur.value) == phrase


@pytest.mark.parametrize("champ", ["nom", "organisation", "message"])
def test_un_champ_trop_long_est_refuse_avec_sa_limite(champ: str) -> None:
    with pytest.raises(SaisieInvalide, match=str(LONGUEUR_MAX[champ])):
        _demande(**{champ: "x" * (LONGUEUR_MAX[champ] + 1)})


def test_un_champ_a_sa_longueur_maximale_est_accepte() -> None:
    assert _demande(message="x" * LONGUEUR_MAX["message"]).message is not None
