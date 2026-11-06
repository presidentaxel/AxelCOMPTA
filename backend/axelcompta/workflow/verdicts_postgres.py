"""Verdicts de classement en Postgres (AXE-823)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.rls import appliquer_rls

from .classees import Verdict
from .orm import verdicts_classement as table
from .verdicts import verifier_verdict


class PostgresVerdicts:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def derniers(self, dossier_id: DossierId) -> dict[EcritureId, Verdict]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table.c.ecriture_id, table.c.verdict)
                .where(table.c.dossier_id == dossier_id)
                .order_by(table.c.rang)
            ).all()
        return {EcritureId(e): verifier_verdict(v) for e, v in lignes}

    def noter(
        self,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        verdict: Verdict,
        par: UserId,
        le: datetime,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                table.insert().values(
                    id=str(uuid.uuid4()),
                    dossier_id=dossier_id,
                    ecriture_id=ecriture_id,
                    verdict=verdict,
                    par=par,
                    le=le,
                )
            )
