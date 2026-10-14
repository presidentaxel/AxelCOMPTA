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
    if erreurs:
        raise LiasseIncoherente(" ; ".join(erreurs))
