"""Libellés d'écriture et l'ancien suffixe de catégorie (AXE-848).

Jusqu'au 9 nov. 2026, la synchro collait la catégorie du pipeline au
libellé de la banque : « Paiement carburant (carburant) ». La catégorie
technique finissait dans le FEC (`EcritureLib`) et à l'écran, jusqu'à
« (non_categorise_a_verifier) ». La synchro écrit désormais le libellé de
la banque tel quel, et la catégorie d'origine se lit dans la proposition
enregistrée.

Les écritures déjà passées gardent leur libellé : le grand livre est
immuable (I2). Le suffixe se retire donc à la lecture, partout où un
libellé s'affiche ou s'exporte. Seul un suffixe en minuscules, chiffres et
soulignés est reconnu : un libellé de banque, en majuscules, n'est pas
touché.
"""

from __future__ import annotations

import re

_SUFFIXE_CATEGORIE = re.compile(r"\s+\(([a-z0-9_]+)\)$")


def sans_categorie(libelle: str) -> str:
    """Le libellé sans l'ancien suffixe « (catégorie) »."""
    return _SUFFIXE_CATEGORIE.sub("", libelle)


def categorie_du_suffixe(libelle: str) -> str | None:
    """La catégorie collée par l'ancienne synchro, ou `None`."""
    trouve = _SUFFIXE_CATEGORIE.search(libelle)
    return trouve.group(1) if trouve else None
