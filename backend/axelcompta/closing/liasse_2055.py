"""Totaux du cadre A du 2055-SD (amortissements techniques), millésime 2026.

Mêmes mouvements que le cadre II de la 2033-C : ouverture, dotations,
sorties, clôture. Le cadre B (amortissements dérogatoires) n'est pas
servi : les écritures ne séparent pas le différentiel de durée, le
dégressif et l'exceptionnel. Pas de PDF.
"""

from __future__ import annotations


def amortissements_2055(lignes_2033c: dict[str, int]) -> dict[str, int]:
    """Cases du total général, en euros. Vide sans amortissement."""
    if "576" not in lignes_2033c and "570" not in lignes_2033c:
        return {}
    return {
        "0N": lignes_2033c.get("570", 0),
        "0P": lignes_2033c.get("572", 0),
        "0Q": lignes_2033c.get("574", 0),
        "0R": lignes_2033c.get("576", 0),
    }
