"""Mapping contact Digifactory → dossier du portefeuille. Aucun appel réseau."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.demo_digifactory import (
    dossier_depuis_contact,
    forme_depuis_nature_juridique,
    nom_affiche,
    numero_contact,
    siren_contact,
)
from axelcompta.tenants.statuts import configuration_de

_AUJOURD_HUI = date(2026, 9, 26)


def test_le_numero_de_contact_reste_des_chiffres() -> None:
    assert numero_contact({"nr": 4952}) == "4952"
    assert numero_contact({"nr": " 9012 "}) == "9012"
    with pytest.raises(ValueError):
        numero_contact({"nr": "abc"})


def test_l_id_derive_du_numero() -> None:
    dossier = dossier_depuis_contact({"nr": "4952", "companyName": "Alpha"}, _AUJOURD_HUI)
    assert dossier.id == "DIGI_4952"
    assert dossier.contact_nr == "4952"
    assert dossier.tenant_id == "TENANT_DEMO"


def test_le_nom_prefere_la_societe_puis_la_personne() -> None:
    assert nom_affiche({"companyName": " Alpha ", "firstname": "A"}, "1") == "Alpha"
    assert nom_affiche({"firstname": "Camille", "lastname": "Martin"}, "1") == "Camille Martin"
    assert nom_affiche({}, "7") == "Contact 7"


def test_la_forme_posee_par_defaut_passe_la_matrice() -> None:
    """Digifactory n'envoie pas le statut : SASU à l'IS, sans identité inventée."""
    dossier = dossier_depuis_contact({"nr": "2", "firstname": "Léa"}, _AUJOURD_HUI)
    configuration_de(dossier)
    assert dossier.forme_juridique == "SASU"
    assert dossier.regime_imposition == "IS"
    assert dossier.identite is None
    assert dossier.exercice_debut == date(2026, 1, 1)
    assert dossier.exercice_fin == date(2026, 12, 31)
    assert dossier.mode_acces_bancaire == "gestionnaire"


def test_le_siren_vient_du_champ_ou_des_neuf_premiers_du_siret() -> None:
    assert siren_contact({"siren": "123456789"}) == "123456789"
    assert siren_contact({"siret": "12345678900012"}) == "123456789"
    assert siren_contact({"siren": "123"}) is None
    assert siren_contact({}) is None


def test_la_nature_juridique_insee_donne_la_forme_sans_deviner_la_sasu() -> None:
    assert forme_depuis_nature_juridique("5710") == "SAS"
    assert forme_depuis_nature_juridique("5720") == "SASU"
    assert forme_depuis_nature_juridique("5499") == "SARL"
    assert forme_depuis_nature_juridique("5498") == "EURL"
    assert forme_depuis_nature_juridique("1000") == "EI"
    assert forme_depuis_nature_juridique("5599") is None
