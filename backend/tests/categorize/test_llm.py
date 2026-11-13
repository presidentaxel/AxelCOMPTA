"""AXE-888 : la demande envoyée au LLM et la lecture de sa réponse."""

from __future__ import annotations

import json

from axelcompta.categorize.llm import (
    CONSIGNES,
    DemandeIa,
    cle_libelle,
    lire_reponse,
    schema_reponse,
    texte_demande,
    tranche,
)

CATEGORIES = ["carburant", "repas_et_receptions", "non_categorise_a_verifier"]
DEMANDES = [
    DemandeIa("boulangerie paul", "CB BOULANGERIE PAUL 12/03", -450, "card"),
    DemandeIa("total access", "CB TOTAL ACCESS", -6000, "card"),
]


def test_la_cle_ignore_chiffres_dates_et_casse() -> None:
    assert cle_libelle("CB BOULANGERIE PAUL 12/03") == cle_libelle("cb Boulangerie Paul 14/04")


def test_le_montant_part_en_ordre_de_grandeur() -> None:
    assert [tranche(m) for m in (-450, 2000, -6000, 50_000, 250_000)] == [
        "moins de 10 €",
        "10 à 50 €",
        "50 à 200 €",
        "200 à 1 000 €",
        "plus de 1 000 €",
    ]


def test_la_demande_porte_les_consignes_et_aucun_montant_exact() -> None:
    texte = texte_demande(DEMANDES, CATEGORIES)
    assert texte.startswith(CONSIGNES)
    assert "-6000" not in texte and "60,00" not in texte
    operations = json.loads(texte.split("Opérations :\n", 1)[1])
    assert [o["id"] for o in operations] == [0, 1]
    assert operations[1]["sens"] == "décaissement"


def test_le_schema_ferme_la_liste_des_categories() -> None:
    schema = schema_reponse(CATEGORIES)
    item = schema["properties"]["propositions"]["items"]
    assert item["properties"]["categorie"]["enum"] == CATEGORIES
    assert item["additionalProperties"] is False


def test_la_reponse_hors_cadre_est_ignoree() -> None:
    brut = json.dumps(
        {
            "propositions": [
                {
                    "id": 0,
                    "categorie": "repas_et_receptions",
                    "confiance": 1.7,
                    "justification": "x",
                },
                {"id": 0, "categorie": "carburant", "confiance": 0.9, "justification": "doublon"},
                {"id": 1, "categorie": "inventee", "confiance": 0.9, "justification": "hors liste"},
                {
                    "id": 7,
                    "categorie": "carburant",
                    "confiance": 0.9,
                    "justification": "id inconnu",
                },
            ]
        }
    )
    (seule,) = lire_reponse(brut, DEMANDES, CATEGORIES)
    assert (seule.cle, seule.categorie, seule.confiance) == (
        "boulangerie paul",
        "repas_et_receptions",
        1.0,
    )
