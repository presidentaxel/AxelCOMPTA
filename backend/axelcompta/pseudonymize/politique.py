"""Quand interroger un LLM, et ce qu'il n'a pas le droit de décider seul.

Le LLM ne valide jamais une écriture à lui seul (doc 05 §4). S'il est
appelé, c'est que le ML était sous le seuil : l'accord des deux renforce
la proposition, il ne l'impute pas.
"""

from __future__ import annotations

from dataclasses import dataclass

SEUIL_ML = 0.75


@dataclass(frozen=True, slots=True)
class AvisMl:
    categorie: str
    confiance: float


def faut_interroger_llm(avis: AvisMl | None, seuil: float = SEUIL_ML) -> bool:
    return avis is None or avis.confiance < seuil


def peut_auto_valider(avis: AvisMl | None, seuil: float = SEUIL_ML) -> bool:
    """Vrai seulement si le ML suffit déjà. Un avis LLM n'entre pas ici."""
    return avis is not None and avis.confiance >= seuil


def avis_concordent(avis_ml: AvisMl | None, categorie_llm: str | None) -> bool:
    return avis_ml is not None and categorie_llm is not None and avis_ml.categorie == categorie_llm
