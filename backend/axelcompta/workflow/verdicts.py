"""Verdicts sur un classement existant (AXE-823) : « juste » ou « faux »,
sans écriture. Append-only : le dernier verdict d'une écriture fait foi,
l'historique sert à mesurer la précision (AXE-816)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from axelcompta.core.errors import DomaineError
from axelcompta.core.ids import DossierId, EcritureId, UserId

from .classees import Verdict

VERDICTS: frozenset[str] = frozenset({"juste", "faux"})


class VerdictInvalide(DomaineError):
    pass


def verifier_verdict(verdict: str) -> Verdict:
    if verdict == "juste":
        return "juste"
    if verdict == "faux":
        return "faux"
    raise VerdictInvalide(f"Verdict inconnu : {verdict}.")


class VerdictsRepository(Protocol):
    def derniers(self, dossier_id: DossierId) -> dict[EcritureId, Verdict]: ...

    def derniers_de(
        self, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[EcritureId, Verdict]]: ...

    def noter(
        self,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        verdict: Verdict,
        par: UserId,
        le: datetime,
    ) -> None: ...


class VerdictsMemoire:
    def __init__(self) -> None:
        self._notes: list[tuple[DossierId, EcritureId, Verdict]] = []

    def derniers(self, dossier_id: DossierId) -> dict[EcritureId, Verdict]:
        return self.derniers_de([dossier_id]).get(dossier_id, {})

    def derniers_de(
        self, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[EcritureId, Verdict]]:
        voulus = set(dossier_ids)
        resultat: dict[DossierId, dict[EcritureId, Verdict]] = {}
        for dossier_id, ecriture_id, verdict in self._notes:
            if dossier_id in voulus:
                resultat.setdefault(dossier_id, {})[ecriture_id] = verdict
        return resultat

    def noter(
        self,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        verdict: Verdict,
        par: UserId,
        le: datetime,
    ) -> None:
        self._notes.append((dossier_id, ecriture_id, verdict))
