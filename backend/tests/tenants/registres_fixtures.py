"""Réponses INSEE et RNE pour les tests d'AXE-849.

Les champs INSEE lus ici sont ceux d'une réponse réelle de l'API Sirene
3.11 (2026-11-11) : `uniteLegale` à côté d'un `header`, période courante
en premier, siège dans `etablissement.adresseEtablissement`. La réponse
RNE suit encore la documentation publique : pas de compte INPI pour la
remplacer.
"""

from __future__ import annotations

from typing import Any

SIREN = "987142031"

INSEE_SIREN: dict[str, Any] = {
    "uniteLegale": {
        "siren": SIREN,
        "dateCreationUniteLegale": "2024-03-13",
        "periodesUniteLegale": [
            {
                "dateFin": None,
                "etatAdministratifUniteLegale": "A",
                "denominationUniteLegale": "AMRANI VTC",
                "categorieJuridiqueUniteLegale": "5710",
                "activitePrincipaleUniteLegale": "49.32Z",
                "nicSiegeUniteLegale": "00010",
            }
        ],
    }
}

INSEE_SIRET: dict[str, Any] = {
    "etablissement": {
        "siret": SIREN + "00010",
        "adresseEtablissement": {
            "numeroVoieEtablissement": "14",
            "typeVoieEtablissement": "RUE",
            "libelleVoieEtablissement": "DE LA FONTAINE AU ROI",
            "codePostalEtablissement": "75011",
            "libelleCommuneEtablissement": "PARIS",
        },
    }
}

RNE_SAS_PLURIPERSONNELLE: dict[str, Any] = {
    "siren": SIREN,
    "formality": {
        "content": {
            "personneMorale": {
                "identite": {
                    "entreprise": {"denomination": "AMRANI VTC", "formeJuridique": "5710"},
                    "description": {
                        "montantCapital": 1000.0,
                        "indicateurAssocieUnique": False,
                    },
                },
                "adresseEntreprise": {
                    "adresse": {
                        "numVoie": "14",
                        "typeVoie": "RUE",
                        "voie": "DE LA FONTAINE AU ROI",
                        "codePostal": "75011",
                        "commune": "PARIS",
                    }
                },
                "composition": {
                    "pouvoirs": [
                        {
                            "individu": {
                                "descriptionPersonne": {"nom": "AMRANI", "prenoms": ["Karim"]}
                            }
                        }
                    ]
                },
            }
        }
    },
}
