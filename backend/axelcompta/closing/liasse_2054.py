"""Totaux du tableau 2054-SD millésime 2026 (notice 2032-NOT-SD).

Mêmes mouvements que la 2033-C : ouverture, entrées, sorties, clôture.
Pas de réévaluation ni de virement de poste à poste dans les écritures,
donc ces deux colonnes restent à zéro et la valeur d'origine finale
égale le brut de clôture. Les lignes par catégorie ne sont pas servies :
leurs codes ne sont pas repris ici. Pas de PDF.
"""

from __future__ import annotations

from .liasse_2033_annexes import Mouvements, immobilisations_2033c


def immobilisations_2054(mouvements: Mouvements) -> dict[str, int]:
    """Cases du total général, en euros. Vide sans immobilisation."""
    lignes = immobilisations_2033c(mouvements)
    if "496" not in lignes and "490" not in lignes:
        return {}
    cloture = lignes.get("496", 0)
    return {
        "0G": lignes.get("490", 0),
        "0H": 0,
        "0J": lignes.get("492", 0),
        "I4": 0,
        "0K": lignes.get("494", 0),
        "0L": cloture,
        "0M": cloture,
    }
