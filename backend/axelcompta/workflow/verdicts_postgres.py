"""Verdicts de classement en Postgres (AXE-823)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
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
        return self.derniers_de([dossier_id]).get(dossier_id, {})

    def derniers_de(
        self, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[EcritureId, Verdict]]:
        """Une requête pour le portefeuille : changer de filtre ne relit pas
        un dossier après l'autre (AXE-824). Le dernier rang fait foi."""
        if not dossier_ids:
            return {}
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table.c.dossier_id, table.c.ecriture_id, table.c.verdict)
                .where(table.c.dossier_id.in_(list(dossier_ids)))
                .order_by(table.c.rang)
            ).all()
        resultat: dict[DossierId, dict[EcritureId, Verdict]] = {}
        for dossier_id, ecriture_id, verdict in lignes:
            notes = resultat.setdefault(DossierId(dossier_id), {})
            notes[EcritureId(ecriture_id)] = verifier_verdict(verdict)
        return resultat

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
