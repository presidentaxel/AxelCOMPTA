"""Bilan 2050 (actif) et 2051 (passif) du régime réel normal, millésime 2026.

Même principe que `liasse_2033` : montants en euros entiers, totaux calculés
sur les lignes déjà arrondies, écart d'arrondi absorbé. Les codes sont ceux
du formulaire (notice 2032-NOT-SD). Pas de PDF : le renderer CERFA du réel
normal n'est pas choisi (ADR-006). La 2033 reste la liasse servie par défaut.
"""

from __future__ import annotations

from collections import defaultdict

from axelcompta.core.errors import DomaineError
from axelcompta.core.pcg import nature_depuis_compte

from .impot_societes import arrondir_euros
from .liasse_2033 import Balance
from .rubriques_2033 import rubrique

# (brut, amortissements) — notice 2050-SD 2026.
IMMOBILISE = (
    ("AB", "AC"),
    ("CX", "CQ"),
    ("AF", "AG"),
    ("AH", "AI"),
    ("AJ", "AK"),
    ("AL", "AM"),
    ("AN", "AO"),
    ("AP", "AQ"),
    ("AR", "AS"),
    ("AT", "AU"),
    ("AV", "AW"),
    ("CS", "CT"),
    ("CU", "CV"),
    ("BB", "BC"),
    ("BD", "BE"),
    ("BF", "BG"),
    ("BH", "BI"),
)
CIRCULANT = (
    ("BL", "BM"),
    ("BN", "BO"),
    ("BP", "BQ"),
    ("BR", "BS"),
    ("BT", "BU"),
    ("BV", "BW"),
    ("BX", "BY"),
    ("BZ", "CA"),
    ("CB", "CC"),
    ("CD", "CE"),
    ("CF", "CG"),
    ("CH", "CI"),
)
CAPITAUX = ("DA", "DB", "DC", "DD", "DE", "DF", "DG", "DH", "DI", "DJ", "DK")
AUTRES_FONDS = ("DM", "DN")
PROVISIONS = ("DP", "DQ")
DETTES = ("DS", "DT", "DU", "DV", "D1", "DW", "DX", "DY", "DZ", "EA", "EB")

ACTIF_BRUT: dict[str, str] = {
    "207": "AH",
    "232": "AL",
    "237": "AL",
    "20": "AJ",
    "211": "AN",
    "212": "AN",
    "213": "AP",
    "214": "AP",
    "215": "AR",
    "231": "AV",
    "238": "AV",
    "218": "AT",
    "22": "AR",
    "21": "AT",
    "23": "AV",
    "261": "CS",
    "26": "BD",
    "27": "BH",
    "31": "BL",
    "32": "BL",
    "33": "BN",
    "34": "BP",
    "35": "BR",
    "37": "BT",
    "3": "BL",
    "409": "BV",
    "411": "BX",
    "413": "BX",
    "416": "BX",
    "418": "BX",
    "109": "CB",
    "486": "CH",
    "50": "CD",
}
ACTIF_AMORT: dict[str, str] = {
    "2807": "AI",
    "2907": "AI",
    "280": "AK",
    "290": "AK",
    "2811": "AO",
    "2812": "AO",
    "2813": "AQ",
    "2814": "AQ",
    "2815": "AS",
    "2818": "AU",
    "281": "AU",
    "282": "AW",
    "291": "AU",
    "293": "AW",
    "296": "CT",
    "297": "BI",
    "39": "BM",
    "491": "BY",
    "59": "CE",
}
PASSIF: dict[str, str] = {
    "101": "DA",
    "108": "DA",
    "104": "DB",
    "105": "DC",
    "1061": "DD",
    "1063": "DE",
    "1064": "DF",
    "106": "DG",
    "10": "DA",
    "11": "DH",
    "13": "DJ",
    "14": "DK",
    "158": "DQ",
    "15": "DP",
    "164": "DU",
    "165": "DV",
    "16": "DU",
    "17": "DV",
    "419": "DW",
    "401": "DX",
    "403": "DX",
    "408": "DX",
    "404": "DZ",
    "405": "DZ",
    "487": "EB",
}
SELON_SIGNE: dict[str, tuple[str, str]] = {
    "51": ("CF", "DU"),
    "53": ("CF", "DU"),
    "54": ("CF", "DU"),
    "58": ("CF", "DU"),
    "5": ("CF", "DU"),
    "42": ("BZ", "DY"),
    "43": ("BZ", "DY"),
    "44": ("BZ", "DY"),
    "455": ("BZ", "EA"),
    "457": ("BZ", "EA"),
    "4": ("BZ", "EA"),
}


class CompteSansPoste2050(DomaineError):
    """Un compte de bilan n'a pas de ligne au 2050 ou au 2051."""


def _selon_signe(compte: str) -> tuple[str, str] | None:
    for longueur in range(len(compte), 0, -1):
        paire = SELON_SIGNE.get(compte[:longueur])
        if paire is not None:
            return paire
    return None


def _poste(compte: str, solde: int) -> tuple[str, int]:
    for table, signe in ((ACTIF_AMORT, -1), (ACTIF_BRUT, 1), (PASSIF, -1)):
        code = rubrique(compte, table)
        if code is not None:
            return code, signe * solde
    paire = _selon_signe(compte)
    if paire is None:
        raise CompteSansPoste2050(f"compte {compte} : aucun poste du 2050")
    return (paire[0], solde) if solde >= 0 else (paire[1], -solde)


def _ventiler(balance: Balance) -> dict[str, int]:
    centimes: dict[str, int] = defaultdict(int)
    for compte, solde in balance.items():
        if not solde or nature_depuis_compte(compte) != "autre":
            continue
        if compte.startswith("12"):
            # Résultat antérieur repris en à-nouveaux : report (DH), pas DI.
            centimes["DH"] += -solde
            continue
        code, montant = _poste(compte, solde)
        centimes[code] += montant
    return centimes


def _somme(lignes: dict[str, int], codes: tuple[str, ...]) -> int:
    return sum(lignes.get(code, 0) for code in codes)


def _totaux(lignes: dict[str, int]) -> None:
    for groupe, brut, amort in ((IMMOBILISE, "BJ", "BK"), (CIRCULANT, "CJ", "CK")):
        lignes[brut] = sum(lignes.get(code, 0) for code, _ in groupe)
        lignes[amort] = sum(lignes.get(code, 0) for _, code in groupe)
    lignes["CO"] = lignes.get("AA", 0) + lignes["BJ"] + lignes["CJ"]
    lignes["1A"] = lignes["BK"] + lignes["CK"]
    lignes["DL"] = _somme(lignes, CAPITAUX)
    lignes["DO"] = _somme(lignes, AUTRES_FONDS)
    lignes["DR"] = _somme(lignes, PROVISIONS)
    lignes["EC"] = _somme(lignes, DETTES)
    lignes["EE"] = lignes["DL"] + lignes["DO"] + lignes["DR"] + lignes["EC"] + lignes.get("ED", 0)


def _ajuster(lignes: dict[str, int], centimes: dict[str, int], ecart: int) -> None:
    """Ramène l'écart d'arrondi (actif net − passif) sur la ligne que cela
    éloigne le moins de sa valeur au centime."""
    actif = {brut for brut, _ in IMMOBILISE + CIRCULANT}
    candidats: list[tuple[int, str, int]] = []
    for code, exact in centimes.items():
        if not exact or code == "DI":
            continue
        correction = -ecart if code in actif else ecart
        ajuste = lignes.get(code, 0) + correction
        candidats.append((abs(ajuste * 100 - exact), code, ajuste))
    if not candidats:
        raise BilanDesequilibre2050(f"écart d'arrondi de {ecart} € sans ligne pour l'absorber")
    _, code, ajuste = min(candidats)
    lignes[code] = ajuste


class BilanDesequilibre2050(DomaineError):
    """Actif net du 2050 et passif du 2051 diffèrent de plus que l'arrondi."""


def bilan_2050(balance: Balance, resultat_exercice: int) -> dict[str, int]:
    """`resultat_exercice` = 2033-B ligne 310, repris en DI : le même chiffre
    que le compte de résultat, pas un second calcul."""
    centimes = _ventiler(balance)
    lignes = {code: arrondir_euros(valeur) for code, valeur in centimes.items()}
    lignes["DI"] = resultat_exercice
    _totaux(lignes)
    ecart = (lignes["CO"] - lignes["1A"]) - lignes["EE"]
    if abs(ecart) > len(centimes) + 1:
        raise BilanDesequilibre2050(f"actif net - passif = {ecart} € (hors arrondi)")
    if ecart:
        _ajuster(lignes, centimes, ecart)
        _totaux(lignes)
    return lignes
