"""Cache par dossier en Postgres (AXE-824) : file expert, opérations classées.

Les deux tables ont la même forme. `colonne` est `sujets` ou `operations`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .classees_cache import VERSION_CLASSEES
from .file_expert_cache import VERSION_FILE, SujetsGardes
from .orm import classees_dossier, file_expert_dossier


class PostgresCacheFileExpert:
    def __init__(
        self,
        engine: Engine,
        table: Table | None = None,
        version: int = VERSION_FILE,
        colonne: str = "sujets",
    ) -> None:
        self._engine = engine
        self._table = file_expert_dossier if table is None else table
        self._version = version
        self._colonne = colonne

    def lire(self, dossier_ids: Sequence[DossierId]) -> dict[DossierId, SujetsGardes]:
        if not dossier_ids:
            return {}
        table = self._table
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table).where(table.c.dossier_id.in_(list(dossier_ids)))
            ).all()
        return {
            DossierId(ligne.dossier_id): SujetsGardes(
                ligne.version_source, ligne.version_calcul, list(getattr(ligne, self._colonne))
            )
            for ligne in lignes
        }

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, Any]]
    ) -> None:
        table = self._table
        valeurs = {
            "version_source": version_source,
            "version_calcul": self._version,
            self._colonne: sujets,
            "calcule_le": datetime.now(UTC),
        }
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(table)
                .values(dossier_id=dossier_id, **valeurs)
                .on_conflict_do_update(index_elements=[table.c.dossier_id], set_=valeurs)
            )


def cache_operations_classees(engine: Engine) -> PostgresCacheFileExpert:
    """Opérations classées, invalidées par la version d'agrégat (AXE-824)."""
    return PostgresCacheFileExpert(engine, classees_dossier, VERSION_CLASSEES, "operations")
