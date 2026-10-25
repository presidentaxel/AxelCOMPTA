"""Imputation par un expert : l'écriture d'origine ne change pas.

Une écriture déjà en ledger est contre-passée, puis une nouvelle écriture
reprend les mêmes montants sur le compte choisi. Le compte 512 (banque) et
la TVA (445) restent en place : seule la contrepartie économique bouge.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Set as AbstractSet

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import EcritureId
from axelcompta.ledger.contrepassation import contrepasser, origine
from axelcompta.ledger.models import Ecriture, Journal

_COMPTE = re.compile(r"^\d{3,8}$")


class ImputationRefusee(DomaineError):
    """Le compte est illisible, ou l'écriture ne peut plus être imputée."""


def _a_reclasser(compte: str) -> bool:
    return compte != "512" and not compte.startswith("445")


def preparer_imputation(
    ecriture: Ecriture, compte: str, connus: AbstractSet[EcritureId]
) -> tuple[Ecriture, Ecriture]:
    """Retourne (contre-passation, nouvelle écriture), sans les enregistrer."""
    if _COMPTE.fullmatch(compte) is None or not _a_reclasser(compte):
        raise ImputationRefusee(f"Compte refusé : {compte}")
    if origine(ecriture.id) is not None:
        raise ImputationRefusee("Une contre-passation ne s'impute pas.")
    inverse = contrepasser(ecriture)
    if inverse.id in connus:
        raise ImputationRefusee("Cette écriture est déjà contre-passée.")
    lignes = []
    change = False
    for ligne in ecriture.lignes:
        if _a_reclasser(ligne.compte) and ligne.compte != compte:
            change = True
            lignes.append(dataclasses.replace(ligne, compte=compte))
        else:
            lignes.append(ligne)
    if not change:
        raise ImputationRefusee("L'écriture est déjà sur ce compte.")
    nouvelle = dataclasses.replace(
        ecriture,
        id=EcritureId(f"{ecriture.id}:impute-{compte}"),
        journal=Journal.OD,
        libelle=f"Imputation {ecriture.libelle}",
        reference_piece=str(ecriture.id),
        lignes=tuple(lignes),
    )
    if nouvelle.id in connus:
        raise ImputationRefusee("Cette imputation existe déjà.")
    return inverse, nouvelle
