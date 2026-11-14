"""`CartesRollee` sur Postgres (migration `c1d8e4a72b16`)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import appliquer_rls

from .cartes_rollee import apercu_json, empreintes_json, user_depuis
from .orm import cartes_rollee
from .rapprochement_rollee import UserRollee


def _user(ligne: Row[Any]) -> UserRollee:
    return user_depuis(
        ligne.rollee_user_id,
        ligne.dossier_metadata,
        ligne.empreintes or {},
        ligne.apercu or {},
        ligne.accounts_number,
        ligne.nom,
        ligne.email_masque,
    )


class PostgresCartesRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lire(self, tenant_id: TenantId, branchement_id: str) -> dict[str, UserRollee]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(cartes_rollee).where(
                    cartes_rollee.c.tenant_id == str(tenant_id),
                    cartes_rollee.c.branchement_id == branchement_id,
                )
            ).all()
        return {ligne.rollee_user_id: _user(ligne) for ligne in lignes}

    def du_portefeuille(self, tenant_id: TenantId) -> list[tuple[str, UserRollee]]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(cartes_rollee).where(cartes_rollee.c.tenant_id == str(tenant_id))
            ).all()
        return [(ligne.branchement_id, _user(ligne)) for ligne in lignes]

    def garder(
        self, tenant_id: TenantId, branchement_id: str, user: UserRollee, le: datetime
    ) -> None:
        valeurs = {
            "rollee_user_id": user.user_id,
            "tenant_id": str(tenant_id),
            "branchement_id": branchement_id,
            "dossier_metadata": user.dossier_metadata,
            "empreintes": empreintes_json(user.empreintes),
            "apercu": apercu_json(user.apercu),
            "lu_le": le,
            "accounts_number": user.accounts_number,
            "nom": user.apercu.nom or None,
            "email_masque": user.apercu.email_masque,
        }
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(cartes_rollee)
                .values(valeurs)
                .on_conflict_do_update(
                    index_elements=[cartes_rollee.c.rollee_user_id], set_=valeurs
                )
            )
