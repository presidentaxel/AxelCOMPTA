"""Historique des exercices clos d'un dossier (append-only).

Le dossier ne porte que son exercice en cours ; chaque passage à l'exercice
suivant (`axelcompta.exercices`) laisse ici une ligne : bornes de
l'exercice clos, date, auteur, et ce qui a changé dans la configuration à
l'ouverture du suivant (régime d'imposition, TVA).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from axelcompta.core.errors import Conflit
from axelcompta.core.ids import DossierId


@dataclass(frozen=True, slots=True)
class ExerciceClos:
    dossier_id: DossierId
    debut: date
    fin: date
    clos_le: datetime
    clos_par: str
    changements: tuple[str, ...] = ()
    # Ce que le chauffeur a accepté mot pour mot en validant (doc 06 §5).
    attestation: str | None = None


class ExerciceRepository(ABC):
    @abstractmethod
    def enregistrer(self, exercice: ExerciceClos) -> None:
        """Ajoute ; un exercice déjà clos (même dossier, même début) lève."""

    @abstractmethod
    def lister(self, dossier_id: DossierId) -> tuple[ExerciceClos, ...]:
        """Du plus ancien au plus récent."""


class ExerciceDejaClos(Conflit, ValueError):
    pass


class InMemoryExerciceRepository(ExerciceRepository):
    def __init__(self) -> None:
        self._exercices: list[ExerciceClos] = []

    def enregistrer(self, exercice: ExerciceClos) -> None:
        if any(
            e.dossier_id == exercice.dossier_id and e.debut == exercice.debut
            for e in self._exercices
        ):
            raise ExerciceDejaClos(f"{exercice.dossier_id} : exercice {exercice.debut} déjà clos")
        self._exercices.append(exercice)

    def lister(self, dossier_id: DossierId) -> tuple[ExerciceClos, ...]:
        return tuple(
            sorted(
                (e for e in self._exercices if e.dossier_id == dossier_id), key=lambda e: e.debut
            )
        )
