"""Cycle d'une alerte : ouverte, en instruction, puis une qualification (doc 05 §6.3)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId

_SUIVANTS = {
    "ouverte": frozenset({"en_instruction"}),
    "en_instruction": frozenset({"justifiee", "usage_personnel", "faux_positif"}),
}


class TransitionRefusee(DomaineError):
    """La décision ne suit pas le cycle, ou une justification sans commentaire."""


@dataclass(frozen=True, slots=True)
class EvenementInstruction:
    """Un changement d'état d'une alerte : qui, quoi, quand (AXE-814)."""

    alerte_id: str
    etat: str
    acteur: str
    commentaire: str
    le: datetime


def etat_actuel(evenements: Sequence[EvenementInstruction]) -> str:
    if not evenements:
        return "ouverte"
    return evenements[-1].etat


def transition(etat: str, decision: str, commentaire: str) -> str:
    if decision not in _SUIVANTS.get(etat, frozenset()):
        raise TransitionRefusee(f"Depuis « {etat} », « {decision} » n'est pas une suite.")
    if decision == "justifiee" and not commentaire.strip():
        raise TransitionRefusee("Une justification emporte un commentaire.")
    return decision


class InstructionsRepository(Protocol):
    """Qualifications d'alertes, append-only : l'état d'une alerte est son
    dernier événement. Les alertes sont recalculées par les détecteurs et
    retrouvent leur qualification par leur identifiant stable
    (`{détecteur}:{écriture}`)."""

    def etats(self, dossier_id: DossierId) -> dict[str, str]:
        """État courant des alertes déjà qualifiées ; une absente est ouverte."""
        ...

    def historique(self, dossier_id: DossierId, alerte_id: str) -> tuple[EvenementInstruction, ...]:
        """Du plus ancien au plus récent."""
        ...

    def instruire(
        self,
        dossier_id: DossierId,
        alerte_id: str,
        decision: str,
        acteur: str,
        commentaire: str,
        le: datetime,
    ) -> str:
        """Applique `transition` à l'état courant et ajoute l'événement, d'un
        seul tenant. Lève `TransitionRefusee`."""
        ...


class RegistreInstructions:
    """Dépôt en mémoire (tests). En service : `PostgresInstructions`."""

    def __init__(self) -> None:
        self._faits: dict[tuple[DossierId, str], list[EvenementInstruction]] = {}

    def etats(self, dossier_id: DossierId) -> dict[str, str]:
        return {
            alerte_id: etat_actuel(evenements)
            for (dossier, alerte_id), evenements in self._faits.items()
            if dossier == dossier_id
        }

    def historique(self, dossier_id: DossierId, alerte_id: str) -> tuple[EvenementInstruction, ...]:
        return tuple(self._faits.get((dossier_id, alerte_id), ()))

    def instruire(
        self,
        dossier_id: DossierId,
        alerte_id: str,
        decision: str,
        acteur: str,
        commentaire: str,
        le: datetime,
    ) -> str:
        suivant = transition(
            etat_actuel(self.historique(dossier_id, alerte_id)), decision, commentaire
        )
        self._faits.setdefault((dossier_id, alerte_id), []).append(
            EvenementInstruction(alerte_id, suivant, acteur, commentaire.strip(), le)
        )
        return suivant
