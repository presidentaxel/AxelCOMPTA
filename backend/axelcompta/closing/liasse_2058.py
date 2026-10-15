"""2058-A millésime 2026 : le même passage comptable → fiscal que la 2033-B.

Les cases de total seulement (WA, WS, WR, XH, XI, XJ, XL, XN, XO).
Le détail ligne à ligne des réintégrations n'est pas ventilé : la 2033-B
ne le sépare pas assez pour les cases WE, WJ et suivantes. Pas de PDF.
"""

from __future__ import annotations

from .liasse_2033 import DEDUCTIONS, REINTEGRATIONS


def resultat_2058(fiscal: dict[str, int]) -> dict[str, int]:
    """`fiscal` est le cadre B déjà calculé pour la 2033-B, en euros."""
    return {
        "WA": fiscal.get("312", 0),
        "WS": fiscal.get("314", 0),
        "WR": sum(fiscal.get(code, 0) for code in REINTEGRATIONS),
        "XH": sum(fiscal.get(code, 0) for code in DEDUCTIONS),
        "XI": fiscal.get("352", 0),
        "XJ": fiscal.get("354", 0),
        "XL": fiscal.get("360", 0),
        "XN": fiscal.get("370", 0),
        "XO": fiscal.get("372", 0),
    }
