"""Lots envoyés au LLM et alertes de budget déjà envoyées (AXE-887).

Chaque lot garde ce qu'il a coûté (jetons d'entrée, de sortie, lus en
cache, dollars), son tenant, son dossier et ses libellés normalisés. C'est
la base du budget, des nouvelles tentatives et du tableau mensuel.

Une alerte n'est envoyée qu'une fois par portée, par mois et par seuil.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .budget_llm import Lot


class LotsLlm(Protocol):
    def lister(self, depuis: datetime) -> list[Lot]:
        """Les lots soumis depuis `depuis`, tous dossiers confondus."""
        ...

    def enregistrer(self, lots: Sequence[Lot]) -> None:
        """Ajoute ou remplace, par identifiant."""
        ...


class AlertesLlm(Protocol):
    def marquer(self, portee: str, cle: str, mois: str, seuil: str, le: datetime) -> bool:
        """Vrai si l'alerte est nouvelle (et donc à envoyer)."""
        ...


@dataclass
class LotsLlmMemoire:
    lots: dict[str, Lot] = field(default_factory=dict)

    def lister(self, depuis: datetime) -> list[Lot]:
        return sorted(
            (lot for lot in self.lots.values() if lot.soumis_le >= depuis),
            key=lambda lot: (lot.soumis_le, lot.id),
        )

    def enregistrer(self, lots: Sequence[Lot]) -> None:
        for lot in lots:
            self.lots[lot.id] = lot


@dataclass
class AlertesLlmMemoire:
    envoyees: set[tuple[str, str, str, str]] = field(default_factory=set)

    def marquer(self, portee: str, cle: str, mois: str, seuil: str, le: datetime) -> bool:
        entree = (portee, cle, mois, seuil)
        if entree in self.envoyees:
            return False
        self.envoyees.add(entree)
        return True
