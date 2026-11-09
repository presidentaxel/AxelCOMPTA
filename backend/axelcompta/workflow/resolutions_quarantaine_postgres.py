"""Résolutions de quarantaine en Postgres (AXE-424)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.rls import appliquer_rls

from .orm import resolutions_quarantaine as table
from .quarantaine import ResolutionRefusee
from .resolutions_quarantaine import Resolution


class PostgresResolutions:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, dossier_id: DossierId) -> dict[str, Resolution]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(select(table).where(table.c.dossier_id == dossier_id)).all()
        return {
            ligne.entree_id: Resolution(
                DossierId(ligne.dossier_id),
                ligne.entree_id,
                "accepter" if ligne.decision == "accepter" else "ignorer",
                tuple(EcritureId(e) for e in ligne.ecritures),
                ligne.par,
                ligne.le,
            )
            for ligne in lignes
        }

    def enregistrer(self, resolution: Resolution) -> None:
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    table.insert().values(
                        id=str(uuid.uuid4()),
                        dossier_id=resolution.dossier_id,
                        entree_id=resolution.entree_id,
                        decision=resolution.decision,
                        ecritures=list(resolution.ecritures),
                        par=resolution.par,
                        le=resolution.le,
                    )
                )
        except IntegrityError as erreur:
            raise ResolutionRefusee("Cette opération a déjà été traitée.") from erreur
