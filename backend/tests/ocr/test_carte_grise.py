"""AXE-993 : la carte grise lue par l'OCR remplit le détail du véhicule."""

from __future__ import annotations

from axelcompta.ocr.categories import Contexte
from axelcompta.ocr.documents import CARTE_GRISE
from axelcompta.traitement_documents_import import classer

CARTE: dict[str, object] = {
    "immatriculation": "GH-512-KL",
    "marque": "TOYOTA",
    "modele": "C-HR",
    "date_premiere_immatriculation": "2022-03-12",
    "titulaire": "SAS KERFICE SERVICE",
    "energie": "Hybride",
    "puissance_fiscale": "6",
}
FICHE = Contexte(champs={"denomination": "KERFICE SERVICE", "nom": "Konate"})


def test_une_carte_grise_de_la_societe_remplit_le_detail_du_vehicule() -> None:
    assert CARTE_GRISE.controler(CARTE, FICHE) == []
    assert CARTE_GRISE.champs_fiche(CARTE) == {
        "vehicule_detail": (
            "TOYOTA C-HR, GH-512-KL, 1re immatriculation le 12/03/2022, hybride, 6 CV "
            "(carte grise)."
        )
    }
    # Au nom du dirigeant, ou à l'ancien format : accepté aussi.
    ancienne = {**CARTE, "immatriculation": "1234 AB 75", "titulaire": "M. KONATE Kerfala"}
    assert CARTE_GRISE.controler(ancienne, FICHE) == []


def test_une_immatriculation_ou_un_titulaire_qui_ne_vont_pas() -> None:
    fausse = {**CARTE, "immatriculation": "GH5I2KL", "date_premiere_immatriculation": ""}
    assert CARTE_GRISE.controler(fausse, FICHE) == [
        "Immatriculation lue GH5I2KL : ni AB-123-CD, ni l'ancien format.",
        "Date de première immatriculation : non lue.",
    ]
    loueur = {**CARTE, "titulaire": "ARVAL SERVICE LEASE"}
    (erreur,) = CARTE_GRISE.controler(loueur, FICHE)
    assert erreur.endswith("Véhicule d'un tiers, ou en LOA au nom du loueur ?")


def test_une_carte_grise_se_reconnait_a_son_nom() -> None:
    assert classer("Carte grise Toyota.pdf", b"%PDF") == "carte_grise"
    assert classer("certificat_immatriculation.jpg", b"") == "carte_grise"
