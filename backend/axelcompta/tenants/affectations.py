"""Décisions d'affectation du résultat (append-only) : une par exercice clos.

Le calcul est dans `closing/affectation.py`, l'enchaînement dans
`axelcompta/affectations.py`. Ici, seulement la trace de la décision du
chauffeur : le scénario retenu, les montants, la date et son identité.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from axelcompta.core.errors import Conflit
from axelcompta.core.ids import DossierId


@dataclass(frozen=True, slots=True)
class DecisionAffectation:
    dossier_id: DossierId
    annee_exercice: int
    scenario: str
    dividendes_cts: int
    reserve_legale_cts: int
    decide_le: datetime
    decide_par: str


class AffectationDejaDecidee(Conflit, ValueError):
    pass


class AffectationRepository(ABC):
    @abstractmethod
    def enregistrer(self, decision: DecisionAffectation) -> None:
        """Ajoute ; une seconde décision pour le même exercice lève."""

    @abstractmethod
    def obtenir(self, dossier_id: DossierId, annee_exercice: int) -> DecisionAffectation | None:
        """`None` si aucune décision pour cet exercice."""


class InMemoryAffectationRepository(AffectationRepository):
    def __init__(self) -> None:
        self._decisions: dict[tuple[str, int], DecisionAffectation] = {}

    def enregistrer(self, decision: DecisionAffectation) -> None:
        cle = (decision.dossier_id, decision.annee_exercice)
        if cle in self._decisions:
            raise AffectationDejaDecidee(f"{cle[0]} : exercice {cle[1]} déjà affecté")
        self._decisions[cle] = decision

    def obtenir(self, dossier_id: DossierId, annee_exercice: int) -> DecisionAffectation | None:
        return self._decisions.get((dossier_id, annee_exercice))
