"""Surveillance des seuils de la franchise en base de TVA (doc 06 §7 :
« franchise supportée, surveillance des seuils de bascule »).

Pur : prend le chiffre d'affaires hors taxe de l'année civile, dit où en
est le dossier. Le calcul du chiffre d'affaires reste chez l'appelant (il
lit le grand livre). Les seuils vivent dans `seuils_franchise_tva.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import cache
from pathlib import Path

CHEMIN_SEUILS = Path(__file__).with_name("seuils_franchise_tva.toml")
# Alerte d'approche : à 90 % du seuil de base, il reste en général un ou
# deux mois de recettes d'un chauffeur avant de le franchir.
SEUIL_APPROCHE = 0.9


class EtatFranchise(StrEnum):
    SOUS_LE_SEUIL = "sous_le_seuil"
    APPROCHE = "approche"
    SEUIL_BASE_DEPASSE = "seuil_base_depasse"
    SEUIL_MAJORE_DEPASSE = "seuil_majore_depasse"


@dataclass(frozen=True, slots=True)
class SeuilsFranchise:
    base_cts: int
    majore_cts: int


@dataclass(frozen=True, slots=True)
class SuiviFranchise:
    etat: EtatFranchise
    seuils: SeuilsFranchise
    message: str | None


class MillesimeInconnu(LookupError):
    """Pas de seuils pour cette année : on ne réutilise jamais ceux d'une
    autre année en silence."""


@cache
def _seuils_par_annee(chemin: Path = CHEMIN_SEUILS) -> dict[int, SeuilsFranchise]:
    with chemin.open("rb") as fichier:
        brut = tomllib.load(fichier)
    return {
        int(annee): SeuilsFranchise(v["base_eur"] * 100, v["majore_eur"] * 100)
        for annee, v in brut["annees"].items()
    }


def seuils(annee: int, debut_activite: date | None = None) -> SeuilsFranchise:
    """Seuils de l'année civile, ramenés au prorata des jours restants si
    l'activité a commencé en cours d'année (§ 285)."""
    connus = _seuils_par_annee()
    if annee not in connus:
        raise MillesimeInconnu(f"Les seuils de la franchise de TVA sont inconnus pour {annee}.")
    base = connus[annee]
    if debut_activite is None or debut_activite.year != annee:
        return base
    jours_annee = (date(annee + 1, 1, 1) - date(annee, 1, 1)).days
    restants = (date(annee + 1, 1, 1) - debut_activite).days
    return SeuilsFranchise(
        base.base_cts * restants // jours_annee, base.majore_cts * restants // jours_annee
    )


def suivre_franchise(
    ca_ht_cts: int, annee: int, debut_activite: date | None = None
) -> SuiviFranchise:
    limites = seuils(annee, debut_activite)
    if ca_ht_cts > limites.majore_cts:
        etat = EtatFranchise.SEUIL_MAJORE_DEPASSE
        message = (
            f"Votre chiffre d'affaires {annee} dépasse le seuil le plus haut. "
            "Vous ne facturiez pas la TVA (taxe sur la valeur ajoutée) : "
            "elle est due depuis la date du dépassement."
        )
    elif ca_ht_cts > limites.base_cts:
        etat = EtatFranchise.SEUIL_BASE_DEPASSE
        message = (
            f"Votre chiffre d'affaires {annee} dépasse le seuil. "
            f"Vous pouvez encore ne pas facturer la TVA (taxe sur la valeur ajoutée) "
            f"jusqu'au 31/12/{annee}. Elle sera due à partir du 1er janvier {annee + 1}."
        )
    elif ca_ht_cts >= limites.base_cts * SEUIL_APPROCHE:
        etat = EtatFranchise.APPROCHE
        message = (
            f"Votre chiffre d'affaires {annee} approche le seuil. "
            "Au-delà, la TVA (taxe sur la valeur ajoutée) sera due l'année suivante."
        )
    else:
        etat, message = EtatFranchise.SOUS_LE_SEUIL, None
    return SuiviFranchise(etat=etat, seuils=limites, message=message)
