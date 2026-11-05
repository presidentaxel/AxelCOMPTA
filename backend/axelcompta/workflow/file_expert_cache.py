"""Sujets de la file expert gardés par dossier (AXE-824).

Reconstruire le grand livre de chaque dossier à chaque ouverture coûtait
4 s à 200 dossiers. Les sujets d'un dossier sont gardés avec la version du
dossier (`agregats_dossier.version`, montée par trigger à chaque écriture,
décision, provision, justificatif ou changement du dossier) : seuls les
dossiers dont la version a bougé sont recalculés.

L'état des alertes (qualifiées ou non) ne fait pas partie de ce qui est
gardé : il est appliqué à la lecture, car il change sans écriture.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from axelcompta.core.ids import DossierId

# À monter quand le calcul des sujets change sans écriture (règles, pack,
# libellés) : les lignes d'une autre version sont recalculées.
VERSION_FILE = 1


@dataclass(frozen=True, slots=True)
class SujetsGardes:
    version_source: int
    version_calcul: int
    sujets: list[dict[str, Any]]

    def valables(self, version_source: int) -> bool:
        return self.version_source == version_source and self.version_calcul == VERSION_FILE


class CacheFileExpert(Protocol):
    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, SujetsGardes]: ...

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, Any]]
    ) -> None: ...


class SansCache:
    """Ne garde rien : chaque lecture recalcule (tests, mémoire)."""

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, SujetsGardes]:
        return {}

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, Any]]
    ) -> None:
        return None


class CacheMemoire:
    def __init__(self) -> None:
        self._gardes: dict[DossierId, SujetsGardes] = {}

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, SujetsGardes]:
        return {d: self._gardes[d] for d in dossier_ids if d in self._gardes}

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, Any]]
    ) -> None:
        self._gardes[dossier_id] = SujetsGardes(version_source, VERSION_FILE, sujets)
