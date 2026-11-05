"""Cache de la file expert en Postgres (AXE-824)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .file_expert_cache import VERSION_FILE, SujetsGardes
from .orm import file_expert_dossier as table


class PostgresCacheFileExpert:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, SujetsGardes]:
        if not dossier_ids:
            return {}
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table).where(table.c.dossier_id.in_(list(dossier_ids)))
            ).all()
        return {
            DossierId(ligne.dossier_id): SujetsGardes(
                ligne.version_source, ligne.version_calcul, list(ligne.sujets)
            )
            for ligne in lignes
        }

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, Any]]
    ) -> None:
        valeurs = {
            "version_source": version_source,
            "version_calcul": VERSION_FILE,
            "sujets": sujets,
            "calcule_le": datetime.now(UTC),
        }
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(table)
                .values(dossier_id=dossier_id, **valeurs)
                .on_conflict_do_update(index_elements=[table.c.dossier_id], set_=valeurs)
            )
