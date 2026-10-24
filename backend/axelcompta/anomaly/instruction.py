"""Cycle d'une alerte : ouverte, en instruction, puis une qualification (doc 05 §6.3)."""

from __future__ import annotations

from dataclasses import dataclass

from axelcompta.core.errors import DomaineError

_SUIVANTS = {
    "ouverte": frozenset({"en_instruction"}),
    "en_instruction": frozenset({"justifiee", "usage_personnel", "faux_positif"}),
}


class TransitionRefusee(DomaineError):
    """La décision ne suit pas le cycle, ou une justification sans commentaire."""


@dataclass(frozen=True, slots=True)
class EvenementInstruction:
    alerte_id: str
    etat: str
    acteur: str
    commentaire: str


def etat_actuel(evenements: tuple[EvenementInstruction, ...]) -> str:
    if not evenements:
        return "ouverte"
    return evenements[-1].etat


def transition(etat: str, decision: str, commentaire: str) -> str:
    if decision not in _SUIVANTS.get(etat, frozenset()):
        raise TransitionRefusee(f"Depuis « {etat} », « {decision} » n'est pas une suite.")
    if decision == "justifiee" and not commentaire.strip():
        raise TransitionRefusee("Une justification emporte un commentaire.")
    return decision


class RegistreInstructions:
    """Mémoire des qualifications. Les alertes elles-mêmes sont recalculées."""

    def __init__(self) -> None:
        self._faits: dict[str, list[EvenementInstruction]] = {}

    def etat(self, alerte_id: str) -> str:
        return etat_actuel(tuple(self._faits.get(alerte_id, ())))

    def instruire(self, alerte_id: str, decision: str, acteur: str, commentaire: str) -> str:
        suivant = transition(self.etat(alerte_id), decision, commentaire)
        self._faits.setdefault(alerte_id, []).append(
            EvenementInstruction(alerte_id, suivant, acteur, commentaire.strip())
        )
        return suivant
