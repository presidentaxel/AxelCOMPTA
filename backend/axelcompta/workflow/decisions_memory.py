"""Implémentation en mémoire de DecisionRepository — pour les tests et pour
brancher rapidement les routes avant que la persistance Postgres (doc 17
§9 bloc A, suite) ne soit câblée. Comme `ledger/memory.py` : prouve le
contrat sans dépendre d'une base, l'implémentation réelle viendra à côté,
pas à la place.
"""

from __future__ import annotations

from axelcompta.core.ids import DossierId, EcritureId

from .decisions import AnnotationDev, DecisionHumaine, DecisionRepository


class InMemoryDecisionRepository(DecisionRepository):
    def __init__(self) -> None:
        self._decisions: dict[tuple[DossierId, EcritureId], list[DecisionHumaine]] = {}
        self._annotations: dict[DossierId, list[AnnotationDev]] = {}

    def enregistrer_decision(self, decision: DecisionHumaine) -> None:
        cle = (decision.dossier_id, decision.ecriture_id)
        self._decisions.setdefault(cle, []).append(decision)

    def decision_courante(
        self, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> DecisionHumaine | None:
        historique = self._decisions.get((dossier_id, ecriture_id), [])
        return max(historique, key=lambda d: d.decide_le) if historique else None

    def lister_decisions(self, dossier_id: DossierId) -> tuple[DecisionHumaine, ...]:
        toutes = [
            decision
            for (dos, _), decisions in self._decisions.items()
            if dos == dossier_id
            for decision in decisions
        ]
        return tuple(sorted(toutes, key=lambda d: d.decide_le))

    def enregistrer_annotation(self, annotation: AnnotationDev) -> None:
        self._annotations.setdefault(annotation.dossier_id, []).append(annotation)

    def lister_annotations(self, dossier_id: DossierId) -> tuple[AnnotationDev, ...]:
        return tuple(self._annotations.get(dossier_id, ()))
