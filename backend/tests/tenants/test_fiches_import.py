"""AXE-941 : la fiche d'import d'un chauffeur, champ par champ."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.identite import Adresse
from axelcompta.core.ids import TenantId
from axelcompta.tenants.fiches_import import (
    SECTIONS,
    FicheImport,
    FicheTraitee,
    changer_statut,
    depuis_registre,
    document_import,
    modifier,
    nouvelle_fiche,
    preremplir,
    valider,
)
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
    with pytest.raises(SaisieInvalide, match="SIREN invalide"):
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


def test_modifier_passe_en_traitement_et_une_fiche_traitee_ne_bouge_plus() -> None:
    fiche = modifier(_fiche(), {"email": "k@x.fr", "telephone": ""}, "b@axel.fr", LE)
    assert (fiche.statut, fiche.champs["email"], fiche.maj_par) == (
        "en_traitement",
        "k@x.fr",
        "b@axel.fr",
    )
    assert "telephone" not in fiche.champs
    traitee = changer_statut(fiche, "traitee", "b@axel.fr", LE)
    with pytest.raises(FicheTraitee):
        modifier(traitee, {"email": "autre@x.fr"}, "b@axel.fr", LE)
    with pytest.raises(SaisieInvalide, match="Statut inconnu"):
        changer_statut(fiche, "archivee", "b@axel.fr", LE)
    assert modifier(changer_statut(traitee, "en_traitement", "b", LE), {"email": "a@x.fr"}, "b", LE)


def test_les_registres_remplissent_les_vides_sans_ecraser_une_saisie() -> None:
    assert depuis_registre(_officielle())["siege"] == "3 rue de la Paix, 75002 Paris"
    fiche = preremplir(_fiche(), _officielle(), "b@axel.fr", LE)
    assert fiche.statut == "a_importer"
    assert (fiche.nom, fiche.prenom) == ("Dupont", "Karim")  # saisis, gardés
    assert fiche.champs["denomination"] == "MK DRIVING"
    assert (fiche.champs["cloture"], fiche.champs["premiere_cloture"]) == ("31/12", "2023-12-31")
    assert (fiche.champs["capital"], fiche.champs["forme_juridique"]) == ("1000.00", "SASU")
    assert fiche.registre is not None and fiche.registre.sources == ("insee", "rne")


def test_un_document_garde_son_empreinte_et_sa_categorie() -> None:
    contenu = b"%PDF-1.4 liasse"
    document = document_import(
        "d1", _fiche(), "liasse", 2025, "liasse.pdf", "application/pdf", contenu, "b", LE
    )
    assert (document.taille, document.empreinte) == (
        len(contenu),
        hashlib.sha256(contenu).hexdigest(),
    )
    with pytest.raises(SaisieInvalide, match="Catégorie"):
        document_import("d2", _fiche(), "photo", None, "x.pdf", "", contenu, "b", LE)
    with pytest.raises(SaisieInvalide, match="Exercice"):
        document_import("d3", _fiche(), "fec", 25, "x.txt", "", contenu, "b", LE)


def test_chaque_categorie_a_une_cle_unique_et_des_champs_uniques() -> None:
    assert len({s.cle for s in SECTIONS}) == len(SECTIONS) == 7
    cles = [c.cle for s in SECTIONS for c in s.champs]
    assert len(cles) == len(set(cles))
