"""Résolutions des entrées de quarantaine (AXE-424) : une par entrée,
append-only, avec son auteur et les écritures passées."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axelcompta.core.ids import DossierId, EcritureId

from .quarantaine import Decision, ResolutionRefusee


@dataclass(frozen=True, slots=True)
class Resolution:
    dossier_id: DossierId
    entree_id: str
    decision: Decision
    ecritures: tuple[EcritureId, ...]
    par: str
    le: datetime


class ResolutionsRepository(Protocol):
    def lister(self, dossier_id: DossierId) -> dict[str, Resolution]:
        """Par identifiant d'entrée."""
        ...

    def enregistrer(self, resolution: Resolution) -> None:
        """Lève `ResolutionRefusee` si l'entrée est déjà résolue."""
        ...


class ResolutionsMemoire:
    def __init__(self) -> None:
        self._resolutions: dict[tuple[DossierId, str], Resolution] = {}

    def lister(self, dossier_id: DossierId) -> dict[str, Resolution]:
        return {e: r for (d, e), r in self._resolutions.items() if d == dossier_id}

    def enregistrer(self, resolution: Resolution) -> None:
        cle = (resolution.dossier_id, resolution.entree_id)
        if cle in self._resolutions:
            raise ResolutionRefusee("Cette opération a déjà été traitée.")
        self._resolutions[cle] = resolution
