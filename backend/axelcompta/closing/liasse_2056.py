"""Totaux du 2056-SD (provisions inscrites au bilan), CERFA 2056-SD.

Ouverture, dotations, reprises, clôture, toutes natures confondues.
Les lignes par nature ne sont pas servies. Les amortissements techniques
(comptes 28) restent au 2055. Pas de PDF.
"""

from __future__ import annotations

from .impot_societes import arrondir_euros
from .liasse_2033_annexes import Mouvements

# Provisions réglementées, risques et charges, dépréciations.
# Les 28 sont des amortissements, pas des provisions du 2056.
_PREFIXES = ("14", "15", "29", "39", "49", "59")


def provisions_2056(mouvements: Mouvements) -> dict[str, int]:
    """Total général en euros. Vide s'il n'y a aucune provision."""
    comptes = set(mouvements.ouverture) | set(mouvements.debits) | set(mouvements.credits)
    ouverture = dotations = reprises = 0
    for compte in comptes:
        if not compte.startswith(_PREFIXES):
            continue
        ouverture += -mouvements.ouverture.get(compte, 0)
        dotations += mouvements.credits.get(compte, 0)
        reprises += mouvements.debits.get(compte, 0)
    debut = arrondir_euros(ouverture)
    hausse = arrondir_euros(dotations)
    baisse = arrondir_euros(reprises)
    if debut == 0 and hausse == 0 and baisse == 0:
        return {}
    return {"7C": debut, "UB": hausse, "UC": baisse, "UD": debut + hausse - baisse}
