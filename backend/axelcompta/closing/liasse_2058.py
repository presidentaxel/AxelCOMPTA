"""2058-A millésime 2026 : le même passage comptable → fiscal que la 2033-B.

Les cases de total seulement (WA, WS, WR, XH, XI, XJ, XL, XN, XO).
Le détail ligne à ligne des réintégrations n'est pas ventilé : la 2033-B
ne le sépare pas assez pour les cases WE, WJ et suivantes. Pas de PDF.
"""

from __future__ import annotations

from .liasse_2033 import DEDUCTIONS, REINTEGRATIONS


def deficits_2058(releve_2033d: dict[str, int]) -> dict[str, int]:
    """2058-B, suivi des déficits. Mêmes euros que le cadre II de la 2033-D.

    K4 reprend le 870 de l'exercice précédent. Aucun déficit n'est
    transféré (K4bis). Les indemnités de congés et les provisions non
    déductibles ne sont pas ventilées.
    """
    return {
        "K4": releve_2033d.get("982", 0),
        "K4bis": 0,
        "K5": releve_2033d.get("983", 0),
        "K6": releve_2033d.get("984", 0),
        "YJ": releve_2033d.get("860", 0),
        "YK": releve_2033d.get("870", 0),
    }


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
