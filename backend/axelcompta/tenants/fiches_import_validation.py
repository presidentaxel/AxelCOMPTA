"""Ce que la validation d'une fiche a gardé (AXE-989). Pur.

Le worker vérifie chaque heure les critères de la banque et des plateformes
(`validation_fiches.py`) et garde leurs manques dans le champ
`validation_import` de la fiche. Les catégories et le statut les lisent ici,
sans relire le grand livre : une fiche n'est « traitée » (chauffeur importé)
que si ses données sont à jour.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

CHAMP_VALIDATION = "validation_import"
SECTIONS_VALIDEES = ("banque", "plateformes")
PAS_ENCORE = "Données vérifiées au prochain passage horaire, une fois le dossier créé."


def manques_gardes(champs: Mapping[str, str], section: str) -> list[str] | None:
    """Les manques d'une section gardés sur la fiche ; `None` si jamais
    validée (fiche sans dossier, ou pas encore passée)."""
    try:
        lu = json.loads(champs.get(CHAMP_VALIDATION) or "")
    except ValueError:
        return None
    if not isinstance(lu, dict) or not isinstance(lu.get(section), list):
        return None
    return [str(m) for m in lu[section]]


def manques_de_section(champs: Mapping[str, str], section: str) -> list[str]:
    """Ce qui empêche une section validée d'être complète."""
    if section not in SECTIONS_VALIDEES:
        return []
    gardes = manques_gardes(champs, section)
    return [PAS_ENCORE] if gardes is None else gardes
