"""Profil comportemental d'un dossier : sommes entières, pas un modèle (doc 05 §6.2)."""

from __future__ import annotations

from dataclasses import dataclass

from .models import MouvementSurveille

# En dessous, l'habitude n'est pas établie : on ne compare pas à 3σ.
OBSERVATIONS_MIN = 5


@dataclass(frozen=True, slots=True)
class CumulCategorie:
    """Somme et somme des carrés des sorties d'une catégorie, en centimes."""

    nombre: int
    somme: int
    carres: int


def cumuls_par_categorie(
    mouvements: tuple[MouvementSurveille, ...],
) -> dict[tuple[str, str], CumulCategorie]:
    """Clé (dossier, catégorie). Seules les sorties comptent."""
    nombres: dict[tuple[str, str], int] = {}
    sommes: dict[tuple[str, str], int] = {}
    carres: dict[tuple[str, str], int] = {}
    for mouvement in mouvements:
        if mouvement.montant_centimes >= 0:
            continue
        cle = (mouvement.dossier_id, mouvement.categorie)
        montant = -mouvement.montant_centimes
        nombres[cle] = nombres.get(cle, 0) + 1
        sommes[cle] = sommes.get(cle, 0) + montant
        carres[cle] = carres.get(cle, 0) + montant * montant
    return {cle: CumulCategorie(nombres[cle], sommes[cle], carres[cle]) for cle in nombres}


def ecarte_du_profil(cumul: CumulCategorie, montant: int) -> bool:
    """`montant` (centimes positifs) est-il à plus de 3σ du reste ?

    Le mouvement testé est retiré du cumul. Une habitude sans dispersion
    signale tout montant différent : l'écart est alors infini.
    """
    reste = cumul.nombre - 1
    if reste < OBSERVATIONS_MIN:
        return False
    somme = cumul.somme - montant
    carres = cumul.carres - montant * montant
    dispersion = reste * carres - somme * somme
    if dispersion <= 0:
        return montant * reste != somme
    ecart = reste * montant - somme
    return ecart * ecart > 9 * dispersion
