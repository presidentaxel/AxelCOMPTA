"""Seuils d'imputation par catégorie, choisis pour viser zéro erreur (AXE-871).

La calibration actuelle vient du FEC historique : sur de vrais relevés VTC, le
modèle se trompe encore au-dessus de 0,85 (mesure du 11/11). Ce calcul part
des décisions humaines : pour chaque catégorie, le plus petit seuil au-dessus
duquel toutes les propositions observées étaient justes. Pas assez
d'observations, ou une erreur tout en haut : pas de seuil, le modèle propose
sans jamais imputer seul.

Pur : les observations viennent de l'appelant (décisions et leur contexte).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

MINIMUM_OBSERVATIONS = 20


def seuils_sans_erreur(
    observations: Iterable[tuple[str, float, bool]], minimum: int = MINIMUM_OBSERVATIONS
) -> dict[str, float | None]:
    """`observations` : (catégorie proposée par le modèle, confiance, juste ?).
    Rend, par catégorie, le seuil sans erreur, ou `None` s'il n'y en a pas
    avec au moins `minimum` propositions justes au-dessus."""
    par_categorie: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for categorie, confiance, juste in observations:
        par_categorie[categorie].append((confiance, juste))
    seuils: dict[str, float | None] = {}
    for categorie, vues in par_categorie.items():
        vues.sort(key=lambda v: v[0], reverse=True)
        seuil: float | None = None
        justes = 0
        for confiance, juste in vues:
            if not juste:
                break
            justes += 1
            seuil = confiance
        # Une erreur à la même confiance que le dernier seuil le rend faux.
        erreurs_au_seuil = any(not j and c >= (seuil or 2.0) for c, j in vues)
        seuils[categorie] = seuil if justes >= minimum and not erreurs_au_seuil else None
    return seuils
