"""AXE-846 : la saisie du siège, du capital et des associés, et le
pré-remplissage depuis le registre public."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from axelcompta.core.identite import Adresse, Associe, IdentiteEntreprise
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.identite_saisie import (
    IdentiteInvalide,
    PersonneConnue,
    completer_pre_remplissage,
    pre_remplissage,
    qualite_par_defaut,
    verifier_identite,
)

AUJOURD_HUI = date(2026, 11, 10)


def _avec(**valeurs: object) -> IdentiteEntreprise:
    return dataclasses.replace(IDENTITE_KARIM, **valeurs)  # type: ignore[arg-type]


def _associe(**valeurs: object) -> Associe:
    return dataclasses.replace(IDENTITE_KARIM.associes[0], **valeurs)  # type: ignore[arg-type]


def test_une_identite_complete_passe() -> None:
    verifier_identite(IDENTITE_KARIM, "SASU", AUJOURD_HUI)


@pytest.mark.parametrize(
    ("identite", "message"),
    [
        (_avec(denomination=" "), "nom de la société"),
        (_avec(siren="987142032"), "SIREN"),
        (_avec(nic="123"), "NIC"),
        (_avec(adresse_siege=Adresse("", "", "75011", "Paris")), "rue et la commune du siège"),
        (_avec(adresse_siege=Adresse("1", "rue X", "7501", "Paris")), "code postal du siège"),
        (_avec(capital_social_cts=0), "capital"),
        (_avec(associes=()), "au moins un associé"),
        (_avec(associes=(_associe(civilite="Mr"),)), "Civilité"),
        (_avec(associes=(_associe(date_naissance=AUJOURD_HUI),)), "doit être passée"),
        (_avec(associes=(_associe(nb_titres=0),)), "nombre de titres"),
        (_avec(associes=(_associe(commune_naissance=""),)), "commune de naissance"),
        (_avec(associes=(_associe(qualite=" "),)), "qualité"),
    ],
)
def test_une_valeur_qui_ne_tient_pas_est_refusee(
    identite: IdentiteEntreprise, message: str
) -> None:
    with pytest.raises(IdentiteInvalide, match=message):
        verifier_identite(identite, "SASU", AUJOURD_HUI)


def test_une_sasu_n_a_qu_un_associe_une_sas_peut_en_avoir_plusieurs() -> None:
    deux = _avec(associes=(_associe(), _associe(nom="MARTIN", nb_titres=10)))
    with pytest.raises(IdentiteInvalide, match="associé unique"):
        verifier_identite(deux, "SASU", AUJOURD_HUI)
    verifier_identite(deux, "SAS", AUJOURD_HUI)


def test_une_adresse_a_l_etranger_n_impose_pas_un_code_postal_francais() -> None:
    adresse = Adresse("12", "Avenue Louise", "1050", "Bruxelles", pays="Belgique")
    verifier_identite(_avec(associes=(_associe(adresse=adresse),)), "SASU", AUJOURD_HUI)


def test_qualite_proposee_selon_la_forme() -> None:
    assert (qualite_par_defaut("SASU"), qualite_par_defaut("EURL")) == ("Président", "Gérant")
    assert qualite_par_defaut("EI") == ""


REPONSE_REGISTRE = {
    "results": [
        {
            "siren": "987142031",
            "nom_complet": "AMRANI VTC (AMRANI VTC)",
            "nom_raison_sociale": "AMRANI VTC",
            "activite_principale": "49.32Z",
            "siege": {
                "siret": "98714203100010",
                "numero_voie": "14",
                "indice_repetition": None,
                "type_voie": "RUE",
                "libelle_voie": "DE LA FONTAINE AU ROI",
                "code_postal": "75011",
                "libelle_commune": "PARIS",
                "activite_principale": "49.32Z",
            },
        }
    ]
}


def test_pre_remplissage_depuis_le_registre() -> None:
    pre = pre_remplissage(REPONSE_REGISTRE, "987142031")
    assert pre is not None
    assert (pre.denomination, pre.nic, pre.code_ape) == ("AMRANI VTC", "00010", "49.32Z")
    assert pre.adresse_siege == Adresse("14", "RUE DE LA FONTAINE AU ROI", "75011", "PARIS")


def test_le_registre_ne_pre_remplit_jamais_avec_une_autre_societe() -> None:
    assert pre_remplissage(REPONSE_REGISTRE, "111111111") is None
    assert pre_remplissage({"results": []}, "987142031") is None
    assert pre_remplissage({}, "987142031") is None


def test_une_valeur_absente_du_registre_reste_vide() -> None:
    pre = pre_remplissage({"results": [{"siren": "987142031", "nom_complet": "X"}]}, "987142031")
    assert pre is not None
    assert (pre.denomination, pre.nic, pre.code_ape) == ("X", "", "")
    assert pre.adresse_siege == Adresse("", "", "", "")
    assert pre.capital_social_cts is None
    assert pre.personnes == ()


def test_le_rne_ajoute_le_capital_et_la_personne_sans_inventer_le_reste() -> None:
    pre = pre_remplissage(REPONSE_REGISTRE, "987142031")
    complet = completer_pre_remplissage(
        pre,
        "987142031",
        capital_social_cts=10000,
        personnes=(PersonneConnue("REICHARD", "Arthur", "92160", "ANTONY"),),
    )
    assert complet is not None
    assert complet.capital_social_cts == 10000
    assert complet.nic == "00010"
    assert complet.personnes == (PersonneConnue("REICHARD", "Arthur", "92160", "ANTONY"),)
    assert completer_pre_remplissage(None, "987142031") is None
