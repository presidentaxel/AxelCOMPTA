"""Objectifs V1 de la catégorisation (doc 01 §6), mesurés (AXE-816).

Pur : prend, pour chaque opération d'un jeu étiqueté, ce que le pipeline a
fait (étage, imputation seule ou non, catégorie proposée) et la catégorie
juste ; rend le tableau des objectifs, par étage et par catégorie.

« Recours au LLM » : la part que règles et modèle laissent sans proposition,
c'est-à-dire ce qui irait au LLM dans la cascade règles → modèle → LLM →
humain (AXE-871). Le LLM n'impute jamais : il ne compte pas dans le taux
automatique.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

ETAGE_REGLE = "regle"
ETAGE_MODELE = "modele"
ETAGE_AUCUN = "aucun"


@dataclass(frozen=True, slots=True)
class Observation:
    etage: str  # regle | modele | banque | aucun
    impute: bool  # imputé sans revue humaine
    proposee: str | None
    vraie: str


@dataclass(frozen=True, slots=True)
class Objectif:
    nom: str
    cible: float  # en %
    au_moins: bool  # vrai : « ≥ cible », faux : « ≤ cible »
    mesure: float | None  # en %, None sans donnée

    @property
    def atteint(self) -> bool | None:
        if self.mesure is None:
            return None
        return self.mesure >= self.cible if self.au_moins else self.mesure <= self.cible


def _pourcent(partie: int, total: int) -> float | None:
    return round(100 * partie / total, 1) if total else None


def mesurer(observations: Sequence[Observation]) -> list[Objectif]:
    total = len(observations)
    imputees = [o for o in observations if o.impute]
    justes = sum(1 for o in imputees if o.proposee == o.vraie)
    regles = sum(1 for o in observations if o.etage == ETAGE_REGLE)
    sans_proposition = sum(1 for o in observations if o.etage == ETAGE_AUCUN)
    return [
        Objectif(
            "Catégorisation automatique sans revue", 85.0, True, _pourcent(len(imputees), total)
        ),
        Objectif(
            "Précision des imputations automatiques", 97.0, True, _pourcent(justes, len(imputees))
        ),
        Objectif("Opérations traitées par les règles", 60.0, True, _pourcent(regles, total)),
        Objectif("Recours au LLM", 10.0, False, _pourcent(sans_proposition, total)),
    ]


def par_etage(observations: Sequence[Observation]) -> dict[str, tuple[int, int, int]]:
    """Par étage : (opérations, propositions justes, imputations fausses)."""
    resultat: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for o in observations:
        ligne = resultat[o.etage]
        ligne[0] += 1
        ligne[1] += o.proposee == o.vraie
        ligne[2] += o.impute and o.proposee != o.vraie
    return {etage: (n, j, f) for etage, (n, j, f) in sorted(resultat.items())}


def par_categorie(observations: Sequence[Observation]) -> dict[str, tuple[int, int, int]]:
    """Par catégorie juste : (opérations, imputées seules, imputées justes)."""
    total: Counter[str] = Counter(o.vraie for o in observations)
    imputees: Counter[str] = Counter(o.vraie for o in observations if o.impute)
    justes: Counter[str] = Counter(
        o.vraie for o in observations if o.impute and o.proposee == o.vraie
    )
    return {c: (total[c], imputees[c], justes[c]) for c in sorted(total)}


def tableau(objectifs: Sequence[Objectif], titre: str) -> str:
    """Le tableau Markdown, à coller dans le doc 07 ou dans un ticket."""
    lignes = [
        f"### {titre}",
        "",
        "| Objectif | Cible V1 | Mesuré | Atteint |",
        "| -- | -- | -- | -- |",
    ]
    for o in objectifs:
        cible = f"{'≥' if o.au_moins else '≤'} {o.cible:g} %"
        mesure = "—" if o.mesure is None else f"{o.mesure:g} %"
        atteint = {True: "oui", False: "**non**", None: "—"}[o.atteint]
        lignes.append(f"| {o.nom} | {cible} | {mesure} | {atteint} |")
    return "\n".join(lignes)
