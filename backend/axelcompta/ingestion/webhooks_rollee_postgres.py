"""Webhooks Rollee en Postgres (AXE-820, migration `d6b2f8a4c3e7`)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import evenements_rollee
from .webhooks_rollee import EvenementRollee


class PostgresEvenementsRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def garder(self, evenement: EvenementRollee) -> bool:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                insert(evenements_rollee)
                .values(
                    id=evenement.id,
                    tenant_id=evenement.tenant_id,
                    branchement_id=evenement.branchement_id,
                    type=evenement.type,
                    payload=evenement.payload,
                    recu_le=evenement.recu_le,
                )
                .on_conflict_do_nothing()
            )
        return resultat.rowcount == 1

    def a_traiter(self, tenant_id: TenantId, limite: int) -> list[EvenementRollee]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(evenements_rollee)
                .where(
                    evenements_rollee.c.tenant_id == tenant_id,
                    evenements_rollee.c.traite_le.is_(None),
                )
                .order_by(evenements_rollee.c.recu_le)
                .limit(limite)
            ).all()
        return [
            EvenementRollee(
                id=ligne.id,
                tenant_id=TenantId(ligne.tenant_id),
                branchement_id=ligne.branchement_id,
                type=ligne.type,
                payload=ligne.payload,
                recu_le=ligne.recu_le,
            )
            for ligne in lignes
        ]

    def marquer_traite(self, evenement_id: str, resultat: str, le: datetime) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                update(evenements_rollee)
                .where(evenements_rollee.c.id == evenement_id)
                .values(traite_le=le, resultat=resultat[:200])
            )
