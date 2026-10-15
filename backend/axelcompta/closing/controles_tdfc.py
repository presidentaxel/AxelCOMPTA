"""Contrôles de cohérence entre cases, ceux qu'un dépôt TDFC refuse.

Ils portent sur le pivot déjà calculé (euros entiers dans les cases
`2033A.xxx`, centimes stockés). Un écart arrête la clôture : on ne livre
pas une liasse dont l'actif ne retrouve pas le passif.
"""

from __future__ import annotations

from axelcompta.core.errors import DomaineError

from .models import LiassePivot

PRODUITS_EXPLOITATION = ("210", "214", "218", "222", "224", "226", "230")
CHARGES_EXPLOITATION = ("234", "236", "238", "240", "242", "244", "250", "252", "254", "256", "262")


class LiasseIncoherente(DomaineError):
    """Au moins un contrôle inter-cases a échoué."""


def _euros(cases: dict[str, int], cle: str) -> int:
    return cases.get(cle, 0) // 100


def _noter(erreurs: list[str], ok: bool, message: str) -> None:
    if not ok:
        erreurs.append(message)


def _controler_2033(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2033A.110" not in cases:
        return
    actif_net = _euros(cases, "2033A.110") - _euros(cases, "2033A.112")
    _noter(
        erreurs,
        actif_net == _euros(cases, "2033A.180"),
        "2033-A : l'actif net n'égale pas le passif",
    )
    _noter(
        erreurs,
        _euros(cases, "2033A.136") == _euros(cases, "2033B.310"),
        "2033 : le résultat du bilan n'est pas celui du compte de résultat",
    )
    _noter(
        erreurs,
        _euros(cases, "2033A.NET.110") == actif_net,
        "2033-A : la colonne net ne retranche pas les amortissements",
    )
    produits = sum(_euros(cases, f"2033B.{code}") for code in PRODUITS_EXPLOITATION)
    charges = sum(_euros(cases, f"2033B.{code}") for code in CHARGES_EXPLOITATION)
    _noter(erreurs, _euros(cases, "2033B.232") == produits, "2033-B : total des produits")
    _noter(erreurs, _euros(cases, "2033B.264") == charges, "2033-B : total des charges")
    _noter(
        erreurs,
        _euros(cases, "2033B.270") == produits - charges,
        "2033-B : le résultat d'exploitation n'est pas produits moins charges",
    )


def _controler_2065(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2065.IMPOT" not in cases:
        return
    fiscal = _euros(cases, "2033B.370") - _euros(cases, "2033B.372")
    _noter(
        erreurs,
        cases["2065"] == fiscal * 100,
        "2065 : le résultat fiscal ne reprend pas la 2033-B",
    )
    _noter(
        erreurs,
        cases["2065.IMPOT"] == cases.get("2033B.306", 0),
        "2065 : l'impôt ne reprend pas la case 306",
    )


def _controler_ca3(cases: dict[str, int], erreurs: list[str]) -> None:
    if "CA3.DUE" not in cases:
        return
    due = cases["CA3.COLLECTEE"] - cases["CA3.DEDUCTIBLE"]
    _noter(erreurs, cases["CA3.DUE"] == due, "CA3 : due ≠ collectée − déductible")


_VENTES_2052 = ("FC", "FF", "FI")
_PRODUITS_2052 = ("FL", "FM", "FN", "FO", "FP", "F1", "FQ")
_CHARGES_2052 = ("FS", "FT", "FU", "FV", "FW", "FX", "FY", "FZ", "GA", "GB", "GC", "GD", "G1", "GE")


def _somme(cases: dict[str, int], tableau: str, codes: tuple[str, ...]) -> int:
    return sum(_euros(cases, f"{tableau}.{code}") for code in codes)


def _controler_2052(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2052.FR" not in cases:
        return
    _noter(
        erreurs,
        _euros(cases, "2052.FL") == _somme(cases, "2052", _VENTES_2052),
        "2052 : le chiffre d'affaires net n'est pas la somme des ventes",
    )
    _noter(
        erreurs,
        _euros(cases, "2052.FR") == _somme(cases, "2052", _PRODUITS_2052),
        "2052 : total des produits d'exploitation",
    )
    _noter(
        erreurs,
        _euros(cases, "2052.GF") == _somme(cases, "2052", _CHARGES_2052),
        "2052 : total des charges d'exploitation",
    )
    _noter(
        erreurs,
        _euros(cases, "2052.GG") == _euros(cases, "2052.FR") - _euros(cases, "2052.GF"),
        "2052 : le résultat d'exploitation n'est pas produits moins charges",
    )
    _noter(
        erreurs,
        _euros(cases, "2052.GV") == _euros(cases, "2052.GP") - _euros(cases, "2052.GU"),
        "2052 : le résultat financier",
    )
    courant = (
        _euros(cases, "2052.GG")
        + _euros(cases, "2052.GH")
        - _euros(cases, "2052.GI")
        + _euros(cases, "2052.GV")
    )
    _noter(erreurs, _euros(cases, "2052.GW") == courant, "2052 : le résultat courant")
    _controler_2053(cases, erreurs)


def _controler_2053(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2053.HN" not in cases:
        return
    _noter(
        erreurs,
        _euros(cases, "2053.HI") == _euros(cases, "2053.HD") - _euros(cases, "2053.HH"),
        "2053 : le résultat exceptionnel",
    )
    produits = (
        _euros(cases, "2052.FR")
        + _euros(cases, "2052.GH")
        + _euros(cases, "2052.GP")
        + _euros(cases, "2053.HD")
    )
    charges = (
        _euros(cases, "2052.GF")
        + _euros(cases, "2052.GI")
        + _euros(cases, "2052.GU")
        + _euros(cases, "2053.HH")
        + _euros(cases, "2053.HJ")
        + _euros(cases, "2053.HK")
    )
    _noter(erreurs, _euros(cases, "2053.HL") == produits, "2053 : total des produits")
    _noter(erreurs, _euros(cases, "2053.HM") == charges, "2053 : total des charges")
    _noter(
        erreurs,
        _euros(cases, "2053.HN") == produits - charges,
        "2053 : le bénéfice ou la perte n'est pas produits moins charges",
    )
    _noter(
        erreurs,
        _euros(cases, "2053.HN") == _euros(cases, "2033B.310"),
        "2053 : le résultat n'est pas celui de la 2033-B",
    )


def _controler_2054(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2054.0L" not in cases:
        return
    cloture = (
        _euros(cases, "2054.0G")
        + _euros(cases, "2054.0H")
        + _euros(cases, "2054.0J")
        - _euros(cases, "2054.I4")
        - _euros(cases, "2054.0K")
    )
    _noter(erreurs, _euros(cases, "2054.0L") == cloture, "2054 : la valeur brute de clôture")
    _noter(
        erreurs,
        _euros(cases, "2054.0M") == _euros(cases, "2054.0L"),
        "2054 : la valeur d'origine finale",
    )
    if "2033C.496" in cases:
        _noter(
            erreurs,
            _euros(cases, "2054.0L") == _euros(cases, "2033C.496"),
            "2054 : le brut de clôture n'est pas celui de la 2033-C",
        )


def _controler_2058(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2058A.XN" not in cases and "2058A.XO" not in cases:
        return
    fiscal = (
        _euros(cases, "2058A.WA")
        - _euros(cases, "2058A.WS")
        + _euros(cases, "2058A.WR")
        - _euros(cases, "2058A.XH")
        - _euros(cases, "2058A.XL")
    )
    declare = _euros(cases, "2058A.XN") - _euros(cases, "2058A.XO")
    _noter(erreurs, declare == fiscal, "2058-A : le résultat fiscal ne se retrouve pas")
    _noter(
        erreurs,
        _euros(cases, "2058A.XN") == _euros(cases, "2033B.370"),
        "2058-A : le bénéfice fiscal n'est pas celui de la 2033-B",
    )
    _noter(
        erreurs,
        _euros(cases, "2058A.XO") == _euros(cases, "2033B.372"),
        "2058-A : le déficit fiscal n'est pas celui de la 2033-B",
    )


def _controler_2050(cases: dict[str, int], erreurs: list[str]) -> None:
    if "2050.CO" not in cases:
        return
    actif_net = _euros(cases, "2050.CO") - _euros(cases, "2050.1A")
    _noter(
        erreurs,
        actif_net == _euros(cases, "2050.EE"),
        "2050 : l'actif net n'égale pas le passif du 2051",
    )
    _noter(
        erreurs,
        _euros(cases, "2050.DI") == _euros(cases, "2033B.310"),
        "2051 : le résultat n'est pas celui du compte de résultat",
    )


def controler_liasse(liasse: LiassePivot) -> None:
    erreurs: list[str] = []
    _controler_2033(liasse.cases, erreurs)
    _controler_2065(liasse.cases, erreurs)
    _controler_ca3(liasse.cases, erreurs)
    _controler_2050(liasse.cases, erreurs)
    _controler_2052(liasse.cases, erreurs)
    _controler_2054(liasse.cases, erreurs)
    _controler_2058(liasse.cases, erreurs)
    if erreurs:
        raise LiasseIncoherente(" ; ".join(erreurs))
