"""Mapping contact Digifactory → dossier du portefeuille. Aucun appel réseau."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.demo_digifactory import (
    dossier_depuis_contact,
    nom_affiche,
    numero_contact,
    preparer_dossier,
    siren_contact,
)
from axelcompta.tenants.sirene import FicheSirene
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


def test_preparer_un_dossier_depuis_sirene() -> None:
    """AXE-834 : JAC TRANSPORTS, créée le 13/03/2026, NAF 49.32Z."""
    voulu = dossier_depuis_contact({"nr": "58591", "companyName": "JAC"}, _AUJOURD_HUI)
    fiche = FicheSirene("102473030", "5710", "49.32Z", "A", date(2026, 3, 13))
    dossier, avertissements = preparer_dossier(voulu, fiche, date(2026, 11, 5))
    assert dossier is not None and avertissements == ()
    assert dossier.exercice_debut == date(2026, 3, 13)
    assert dossier.forme_juridique == "SAS"
    assert dossier.a_confirmer == ("exercice", "forme_juridique")


def test_une_societe_cessee_n_a_pas_de_dossier() -> None:
    voulu = dossier_depuis_contact({"nr": "1"}, _AUJOURD_HUI)
    dossier, avertissements = preparer_dossier(
        voulu, FicheSirene("1", "5710", "49.32Z", "C", None), _AUJOURD_HUI
    )
    assert dossier is None
    assert "cessée" in avertissements[0]


def test_une_activite_hors_vtc_est_signalee_et_sans_fiche_tout_est_a_confirmer() -> None:
    """SERENITY GROUPE (70.22Z) : créé mais signalé ; sans fiche, tout est à confirmer."""
    voulu = dossier_depuis_contact({"nr": "4952"}, _AUJOURD_HUI)
    conseil = FicheSirene("501518971", "5710", "70.22Z", "A", date(2007, 12, 13))
    dossier, avertissements = preparer_dossier(voulu, conseil, _AUJOURD_HUI)
    assert dossier is not None and "pas un chauffeur" in avertissements[0]
    sans_fiche, _ = preparer_dossier(voulu, None, _AUJOURD_HUI)
    assert sans_fiche is not None
    assert sans_fiche.a_confirmer == ("exercice", "forme_juridique")
