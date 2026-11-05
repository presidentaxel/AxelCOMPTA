"""Implémentation Postgres de NotificationRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.rls import appliquer_rls

from .notifications import NotificationEnvoyee, NotificationRepository
from .orm import notifications_envoyees as table


class PostgresNotificationRepository(NotificationRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def derniere(self, dossier_id: DossierId, type_: str) -> NotificationEnvoyee | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(table)
                .where(table.c.dossier_id == dossier_id, table.c.type == type_)
                .order_by(table.c.envoye_le.desc())
                .limit(1)
            ).first()
        return None if ligne is None else _depuis_ligne(ligne)

    def lister(self, dossier_id: DossierId, limite: int) -> list[NotificationEnvoyee]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table)
                .where(table.c.dossier_id == dossier_id)
                .order_by(table.c.envoye_le.desc())
                .limit(limite)
            ).all()
        return [_depuis_ligne(ligne) for ligne in lignes]

    def marquer_lues(self, dossier_id: DossierId, maintenant: datetime) -> int:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                update(table)
                .where(table.c.dossier_id == dossier_id, table.c.lue_le.is_(None))
                .values(lue_le=maintenant)
            )
        return resultat.rowcount

    def marquer_lue(
        self, dossier_id: DossierId, notification_id: str, maintenant: datetime
    ) -> bool:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            existe = connexion.execute(
                select(table.c.id).where(
                    table.c.dossier_id == dossier_id,
                    table.c.id == notification_id,
                )
            ).first()
            if existe is None:
                return False
            connexion.execute(
                update(table)
                .where(
                    table.c.dossier_id == dossier_id,
                    table.c.id == notification_id,
                    table.c.lue_le.is_(None),
                )
                .values(lue_le=maintenant)
            )
        return True

    def enregistrer(self, notification: NotificationEnvoyee) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                table.insert().values(
                    id=notification.id,
                    dossier_id=notification.dossier_id,
                    type=notification.type,
                    envoye_le=notification.envoye_le,
                    ecriture_ids=list(notification.ecriture_ids),
                )
            )


def _depuis_ligne(ligne: Row[Any]) -> NotificationEnvoyee:
    return NotificationEnvoyee(
        id=ligne.id,
        dossier_id=DossierId(ligne.dossier_id),
        type=ligne.type,
        envoye_le=ligne.envoye_le,
        ecriture_ids=tuple(EcritureId(i) for i in ligne.ecriture_ids),
        lue_le=ligne.lue_le,
    )
