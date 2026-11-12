"""Indicateurs de catégorisation en production (AXE-900, doc 15 §2).

Pur. Pour chaque opération écrite par la synchro sur la période : l'étage
qui l'a proposée, si elle a été imputée seule ou mise au compte d'attente,
et quand un humain l'a tranchée. On en tire la part de chaque étage, la
part imputée seule, tranchée et encore en attente, et le délai entre la
date de l'opération et son imputation sur un compte définitif (p95, cible
doc 01 §6 : moins de 48 h).

Délai : imputée seule, c'est le passage de la synchro ; à trancher, c'est
la première décision humaine ; encore en attente, c'est l'âge à ce jour
(une file bouchée doit se voir). Les recettes de plateforme qui attendent
leur rapprochement (`CATEGORIES_EN_ATTENTE_DE_SETTLEMENT`) n'en font pas
partie : elles ne sortent pas du compte d'attente par une décision.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from axelcompta.categorize.models import Etage
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT

from .synchro import CATEGORIES_EN_ATTENTE_DE_SETTLEMENT

ETAGES_SUIVIS = ("regle", "modele", "banque", "aucune")
_PAR_ETAGE = {Etage.REGLE.name: "regle", Etage.ML.name: "modele", Etage.BANQUE.name: "banque"}


@dataclass(frozen=True, slots=True)
class OperationSuivie:
    etage: str  # nom d'`Etage`, tel qu'en base
    categorie: str
    date_operation: date
    cree_le: datetime  # passage de la synchro
    a_trancher: bool  # écrite au compte d'attente
    decide_le: datetime | None  # première décision humaine qui la classe


@dataclass(frozen=True, slots=True)
class Indicateurs:
    operations: int
    part_par_etage: dict[str, float]  # en %, clés `ETAGES_SUIVIS`
    part_imputee_seule: float
    part_tranchee: float
    part_en_attente: float
    delai_p95_heures: float | None  # None sans opération mesurable


def etage_suivi(operation: OperationSuivie) -> str:
    if operation.categorie == CATEGORIE_PAR_DEFAUT:
        return "aucune"
    return _PAR_ETAGE.get(operation.etage, "aucune")


def delai_heures(operation: OperationSuivie, maintenant: datetime) -> float | None:
    if operation.a_trancher and operation.categorie in CATEGORIES_EN_ATTENTE_DE_SETTLEMENT:
        return None
    if not operation.a_trancher:
        fin = operation.cree_le
    else:
        fin = operation.decide_le or maintenant
    debut = datetime.combine(operation.date_operation, time(), UTC)
    return max(0.0, (fin - debut).total_seconds() / 3600)


def centile(valeurs: Sequence[float], rang: float) -> float | None:
    """Centile au rang le plus proche (sans interpolation)."""
    if not valeurs:
        return None
    triees = sorted(valeurs)
    return triees[max(0, math.ceil(rang / 100 * len(triees)) - 1)]


def _part(nombre: int, total: int) -> float:
    return round(100 * nombre / total, 1) if total else 0.0


def calculer(operations: Sequence[OperationSuivie], maintenant: datetime) -> Indicateurs:
    total = len(operations)
    etages = Counter(etage_suivi(o) for o in operations)
    tranchees = sum(1 for o in operations if o.a_trancher and o.decide_le is not None)
    en_attente = sum(1 for o in operations if o.a_trancher and o.decide_le is None)
    delais = [d for o in operations if (d := delai_heures(o, maintenant)) is not None]
    p95 = centile(delais, 95)
    return Indicateurs(
        operations=total,
        part_par_etage={etage: _part(etages[etage], total) for etage in ETAGES_SUIVIS},
        part_imputee_seule=_part(total - tranchees - en_attente, total),
        part_tranchee=_part(tranchees, total),
        part_en_attente=_part(en_attente, total),
        delai_p95_heures=None if p95 is None else round(p95, 1),
    )
