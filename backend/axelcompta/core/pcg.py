"""Conventions génériques du Plan Comptable Général (doc 06 §2) — pas
spécifique à un pack métier, donc dans `core` plutôt que dans `packs`.
"""

from __future__ import annotations


def nature_depuis_compte(compte: str) -> str:
    """Convention PCG : classe 6 = charge, classe 7 = produit. Tout le reste
    (immobilisations, capital, tiers...) est hors scope démo."""
    if compte.startswith("6"):
        return "charge"
    if compte.startswith("7"):
        return "produit"
    return "autre"


# Banques (PCG, compte 512). Un dossier a un sous-compte par compte bancaire
# (5121, 5122… : AXE-832) ; `512` seul reste le compte d'une banque inconnue
# et celui des écritures antérieures à la ventilation.
COMPTE_BANQUE = "512"


def est_compte_banque(compte: str) -> bool:
    """`512` et ses sous-comptes. Seule définition du compte de banque : ne
    jamais comparer à la chaîne `"512"` ailleurs."""
    return compte.startswith(COMPTE_BANQUE)
