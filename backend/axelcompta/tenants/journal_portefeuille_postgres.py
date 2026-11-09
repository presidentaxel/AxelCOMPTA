"""Journal du portefeuille en Postgres (AXE-812, migration `b8e4c2d7a613`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId, UserId
from axelcompta.core.rls import appliquer_rls

from .orm import journal_portefeuille


class PostgresJournalPortefeuille:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def noter(
        self, tenant_id: TenantId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                journal_portefeuille.insert().values(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    type_acte=type_acte,
                    reference=reference,
                    acteur=acteur,
                    acte_le=le,
                )
            )
