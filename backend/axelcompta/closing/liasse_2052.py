"""Compte de résultat 2052 et 2053, millésime 2026 (notice 2032-NOT-SD).

Les montants reprennent les lignes déjà arrondies du 2033-B. Le bénéfice
ou la perte (2053 HN) est donc le même chiffre que la ligne 310. Pas de
PDF. Les annexes 2054 à 2059 ne sont pas ici.

Millésime 2026 (règlement ANC 2022-06) : le total des charges
d'exploitation est GF, les autres charges sont en GE, les produits
exceptionnels en HD et les charges exceptionnelles en HH. La balance ne
distingue pas la France de l'export : le chiffre d'affaires est porté
dans la colonne France, et recopié dans le total de la ligne.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from .impot_societes import arrondir_euros
from .liasse_2033 import Balance, compte_de_resultat
from .rubriques_2033 import rubrique_resultat

# Ligne 2033-B → case 2052/2053, quand la ligne du formulaire 2026 a le
# même périmètre. 230 et 256 sont éclatées plus bas.
_LIGNE_VERS_CASE = {
    "210": "FA",
    "214": "FD",
    "218": "FG",
    "222": "FM",
    "224": "FN",
    "226": "FO",
    "234": "FS",
    "236": "FT",
    "238": "FU",
    "240": "FV",
    "242": "FW",
    "244": "FX",
    "250": "FY",
    "252": "FZ",
    "254": "GA",
    "262": "GE",
    "280": "GP",
    "294": "GU",
    "290": "HD",
    "300": "HH",
    "306": "HK",
}

_PRODUITS = ("FL", "FM", "FN", "FO", "FP", "F1", "FQ")
_CHARGES = ("FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ", "GA", "GB", "GC", "GD", "G1", "GE")
_CASES_2053 = frozenset({"HD", "HH", "HJ", "HK"})
_TOTAUX_2052 = frozenset({"FJ", "FL", "FR", "GF", "GG", "GP", "GU", "GV", "GW"})


def compte_2052(balance: Balance) -> tuple[dict[str, int], dict[str, int]]:
    """(cases 2052, cases 2053), en euros entiers."""
    lignes = compte_de_resultat(balance)
    detail = {case: lignes[code] for code, case in _LIGNE_VERS_CASE.items() if lignes.get(code)}
    _eclater(detail, balance, lignes, "230", "FQ", _case_autres_produits)
    _eclater(detail, balance, lignes, "256", "GD", _case_dotation)
    return _totaux(detail)


def _case_autres_produits(compte: str) -> str:
    """2026 : FP ne contient plus les transferts de charges (79)."""
    return "FP" if compte.startswith("78") else "FQ"


def _case_dotation(compte: str) -> str:
    if compte.startswith("6815"):
        return "GB"
    if compte.startswith("6816"):
        return "GC"
    return "GD"


def _eclater(
    detail: dict[str, int],
    balance: Balance,
    lignes: dict[str, int],
    code: str,
    repli: str,
    choix: Callable[[str], str],
) -> None:
    total = lignes.get(code, 0)
    parts = _repartir(balance, code, total, choix)
    if parts:
        for case, montant in parts.items():
            detail[case] = detail.get(case, 0) + montant
    elif total:
        detail[repli] = detail.get(repli, 0) + total


def _repartir(
    balance: Balance, code_ligne: str, total: int, choix: Callable[[str], str]
) -> dict[str, int]:
    """Éclate une ligne 2033-B. Si l'arrondi des parts n'en retrouve pas
    le total, on renvoie vide : l'appelant met tout sur une seule case,
    pour que HN reste égal à 310."""
    brut: dict[str, int] = defaultdict(int)
    for compte, solde in balance.items():
        if not compte or compte[0] not in "67":
            continue
        code, signe = rubrique_resultat(compte)
        if code == code_ligne:
            brut[choix(compte)] += signe * solde
    euros = {case: arrondir_euros(centimes) for case, centimes in brut.items()}
    if sum(euros.values()) != total:
        return {}
    return {case: montant for case, montant in euros.items() if montant}


def _totaux(detail: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    detail["FC"] = detail.get("FA", 0)
    detail["FF"] = detail.get("FD", 0)
    detail["FI"] = detail.get("FG", 0)
    detail["FJ"] = detail.get("FA", 0) + detail.get("FD", 0) + detail.get("FG", 0)
    detail["FL"] = detail["FC"] + detail["FF"] + detail["FI"]
    fr = sum(detail.get(code, 0) for code in _PRODUITS)
    gf = sum(detail.get(code, 0) for code in _CHARGES)
    gp, gu = detail.get("GP", 0), detail.get("GU", 0)
    gg, gv = fr - gf, gp - gu
    gw = gg + detail.get("GH", 0) - detail.get("GI", 0) + gv
    hd, hh, hk = detail.get("HD", 0), detail.get("HH", 0), detail.get("HK", 0)
    hl = fr + detail.get("GH", 0) + gp + hd
    hm = gf + detail.get("GI", 0) + gu + hh + detail.get("HJ", 0) + hk
    expl = {cle: valeur for cle, valeur in detail.items() if cle not in _CASES_2053}
    expl.update(FR=fr, GF=gf, GG=gg, GP=gp, GU=gu, GV=gv, GW=gw)
    suite = {"HD": hd, "HH": hh, "HI": hd - hh, "HK": hk, "HL": hl, "HM": hm, "HN": hl - hm}
    if detail.get("HJ"):
        suite["HJ"] = detail["HJ"]
    return _sans_zeros(expl, _TOTAUX_2052), _sans_zeros(suite, frozenset({"HI", "HL", "HM", "HN"}))


def _sans_zeros(cases: dict[str, int], gardes: frozenset[str]) -> dict[str, int]:
    return {cle: valeur for cle, valeur in cases.items() if valeur or cle in gardes}
