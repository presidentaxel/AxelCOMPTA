"""AXE-941 : la fiche d'import d'un chauffeur, champ par champ."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import UTC, date, datetime

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.identite import Adresse
from axelcompta.core.ids import TenantId
from axelcompta.tenants.fiches_import import (
    SECTIONS,
    FicheImport,
    annuler,
    depuis_registre,
    document_import,
    modifier,
    nouvelle_fiche,
    preremplir,
    valider,
)
from axelcompta.tenants.fiches_import_calculs import numero_tva
from axelcompta.tenants.registres import FicheOfficielle, PersonneOfficielle

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
SIREN = "552100554"
T = TenantId("TENANT_DEMO")


def _fiche(siren: str = SIREN) -> FicheImport:
    return nouvelle_fiche("f1", T, "Dupont", "Karim", siren, "equipe@axel.fr", LE)


def _officielle() -> FicheOfficielle:
    return FicheOfficielle(
        siren=SIREN,
        lu_le=date(2026, 11, 16),
        sources=("insee", "rne"),
        denomination="MK DRIVING",
        forme_juridique="SASU",
        siege=Adresse("3", "rue de la Paix", "75002", "Paris"),
        capital_cts=100_000,
        personnes=(PersonneOfficielle("MARTIN", "Karim Ali"),),
        date_creation=date(2023, 3, 15),
        code_naf="49.32Z",
        cloture="31/12",
        premiere_cloture=date(2023, 12, 31),
    )


def test_une_fiche_s_ouvre_avec_le_nom_ou_le_prenom_et_un_siren_valide() -> None:
    fiche = _fiche()
    assert (fiche.statut, fiche.champs["siren"], fiche.champs["nom"]) == (
        "a_importer",
        SIREN,
        "Dupont",
    )
    assert nouvelle_fiche("f2", T, "", "Karim", "", "x", LE).champs == {"prenom": "Karim"}
    with pytest.raises(SaisieInvalide, match="nom ou le prénom"):
        nouvelle_fiche("f3", T, " ", "", "", "x", LE)
    with pytest.raises(SaisieInvalide, match="SIREN ou SIRET invalide"):
        nouvelle_fiche("f4", T, "Dupont", "", "123456789", "x", LE)


def test_chaque_type_de_champ_est_range_ou_refuse_avec_un_message() -> None:
    rangees = valider(
        {
            "capital": "1 250,5 €",
            "cloture": "31.12",
            "date_creation": "2023-03-15",
            "plateformes": "uber,bolt,uber",
            "telephone": "06 12 34 56 78",
            "siren": "552 100 554",
            "email": "",
        }
    )
    assert rangees == {
        "capital": "1250.50",
        "cloture": "31/12",
        "date_creation": "2023-03-15",
        "plateformes": "uber,bolt",
        "telephone": "06 12 34 56 78",
        "siren": SIREN,
        "email": "",
    }
    for saisie, message in (
        ({"inconnu": "x"}, "Champ inconnu"),
        ({"email": "pas-un-mail"}, "E-mail"),
        ({"cloture": "31/13"}, "jour et mois"),
        ({"date_creation": "15/03/2023"}, "une date"),
        ({"forme_juridique": "SA"}, "valeur inconnue"),
        ({"capital": "mille"}, "montant"),
        ({"option_ir_debut": "25"}, "une année"),
    ):
        with pytest.raises(SaisieInvalide, match=message):
            valider(saisie)


def test_modifier_range_les_champs_et_annuler_garde_la_trace() -> None:
    fiche = modifier(_fiche(), {"email": "k@x.fr", "telephone": ""}, "b@axel.fr", LE)
    assert (fiche.champs["email"], fiche.maj_par) == ("k@x.fr", "b@axel.fr")
    assert "telephone" not in fiche.champs
    annulee = annuler(fiche, "b@axel.fr", LE)
    assert (annulee.annulee_le, annulee.annulee_par) == (LE, "b@axel.fr")


def test_la_tva_et_l_exercice_en_cours_se_deduisent_sans_ecraser_une_saisie() -> None:
    """AXE-947 : FR + clé + SIREN ; exercice en cours d'après la clôture."""
    fiche = modifier(_fiche(), {"date_creation": "2023-03-15", "cloture": "31/12"}, "b", LE)
    assert fiche.champs["numero_tva"] == "FR96552100554"
    assert (fiche.champs["exercice_debut"], fiche.champs["exercice_fin"]) == (
        "2026-01-01",
        "2026-12-31",
    )
    decale = modifier(fiche, {"cloture": "30/06"}, "b", LE)
    assert (decale.champs["exercice_debut"], decale.champs["exercice_fin"]) == (
        "2026-07-01",
        "2027-06-30",
    )
    saisi = modifier(fiche, {"exercice_debut": "2026-02-01"}, "b", LE)
    assert modifier(saisi, {"cloture": "30/06"}, "b", LE).champs["exercice_debut"] == "2026-02-01"


def test_les_registres_remplissent_les_vides_sans_ecraser_une_saisie() -> None:
    assert depuis_registre(_officielle())["siege"] == "3 rue de la Paix, 75002 Paris"
    fiche = preremplir(_fiche(), _officielle(), "b@axel.fr", LE)
    assert (fiche.nom, fiche.prenom) == ("Dupont", "Karim")  # saisis, gardés
    assert fiche.champs["denomination"] == "MK DRIVING"
    assert (fiche.champs["cloture"], fiche.champs["premiere_cloture"]) == ("31/12", "2023-12-31")
    assert (fiche.champs["capital"], fiche.champs["forme_juridique"]) == ("1000.00", "SASU")
    assert fiche.registre is not None and fiche.registre.sources == ("insee", "rne")


def test_un_document_garde_son_emplacement_et_son_empreinte() -> None:
    contenu = b"%PDF-1.4 liasse"
    document = document_import(
        "d1", _fiche(), "reprise:liasse:2025", "liasse.pdf", "application/pdf", contenu, "b", LE
    )
    assert (document.categorie, document.exercice, document.emplacement) == (
        "liasse",
        2025,
        "reprise:liasse:2025",
    )
    assert document.empreinte == hashlib.sha256(contenu).hexdigest()
    for emplacement, message in (
        ("reprise:photo", "Catégorie"),
        ("ailleurs:kbis", "Emplacement inconnu"),
        ("reprise:fec:25", "Exercice"),
    ):
        with pytest.raises(SaisieInvalide, match=message):
            document_import("d2", _fiche(), emplacement, "x.pdf", "", contenu, "b", LE)


def test_chaque_categorie_a_une_cle_unique_et_des_champs_uniques() -> None:
    assert len({s.cle for s in SECTIONS}) == len(SECTIONS) == 7
    cles = [c.cle for s in SECTIONS for c in s.champs]
    assert len(cles) == len(set(cles))


def test_un_siret_donne_aussi_le_siren() -> None:
    assert valider({"siren": "552 100 554 00013"}) == {"siren": SIREN, "siret": "55210055400013"}
    with pytest.raises(SaisieInvalide, match="clé de contrôle"):
        valider({"siren": "55210055400014"})


def test_un_siren_corrige_remplace_ce_qui_venait_du_registre_pas_la_saisie() -> None:
    fiche = preremplir(_fiche(), _officielle(), "b", LE)
    fiche = modifier(fiche, {"siege": "Saisi à la main"}, "b", LE)
    autre = dataclasses.replace(_officielle(), denomination="BONNE SOCIETE", siege=None)
    relue = preremplir(fiche, autre, "b", LE)
    assert relue.champs["denomination"] == "BONNE SOCIETE"
    assert relue.champs["siege"] == "Saisi à la main"
    assert json.loads(relue.champs["associes"])[0]["fonction"] == "president"


def test_la_cle_de_tva_suit_la_formule_officielle() -> None:
    """Vérifié auprès de VIES le 16/11 : FR64 443061841 est valide."""
    assert numero_tva("443061841") == "FR64443061841"
    assert numero_tva("12345") is None


def test_relire_les_registres_retire_un_associe_lu_en_double_avant() -> None:
    """AXE-951 : une fiche préremplie avec la même personne deux fois (lecture
    d'avant) n'en garde qu'une après relecture, si personne ne l'a modifiée."""
    double = PersonneOfficielle("AGBO", "Toussaint W")
    avant = dataclasses.replace(_officielle(), personnes=(double, double))
    fiche = preremplir(_fiche(), avant, "b", LE)
    assert len(json.loads(fiche.champs["associes"])) == 2

    apres = dataclasses.replace(
        _officielle(),
        personnes=(
            PersonneOfficielle("AGBO", "Toussaint W", prenom_usuel="Toussaint", roles=("73",)),
        ),
    )
    (associe,) = json.loads(preremplir(fiche, apres, "b", LE).champs["associes"])
    assert (associe["prenom"], associe["fonction"]) == ("Toussaint", "president")
