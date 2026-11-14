"""`AnnuaireRollee` sur Postgres (AXE-919, migration `f3b7d9e1a2c4`).

Écrit par le passage de rapprochement, avec la connexion propriétaire ; lu
par l'API avec le rôle web, sous la RLS du portefeuille.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import appliquer_rls

from .annuaire_rollee import FicheAnnuaire
from .orm import annuaire_rollee


def _fiche(ligne: Row[Any]) -> FicheAnnuaire:
    maj = ligne.maj_le if ligne.maj_le.tzinfo is not None else ligne.maj_le.replace(tzinfo=UTC)
    return FicheAnnuaire(
        rollee_user_id=ligne.rollee_user_id,
        tenant_id=TenantId(ligne.tenant_id),
        branchement_id=ligne.branchement_id,
        nom=ligne.nom,
        plateformes=tuple(ligne.plateformes or ()),
        email_masque=ligne.email_masque,
        maj_le=maj,
    )


def _valeurs(fiche: FicheAnnuaire) -> dict[str, Any]:
    return {
        "rollee_user_id": fiche.rollee_user_id,
        "tenant_id": str(fiche.tenant_id),
        "branchement_id": fiche.branchement_id,
        "nom": fiche.nom,
        "plateformes": list(fiche.plateformes),
        "email_masque": fiche.email_masque,
        "maj_le": fiche.maj_le,
    }


class PostgresAnnuaireRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def fiches(self, tenant_id: TenantId) -> list[FicheAnnuaire]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(annuaire_rollee).where(annuaire_rollee.c.tenant_id == str(tenant_id))
            ).all()
        return [_fiche(ligne) for ligne in lignes]

    def fiche(self, tenant_id: TenantId, rollee_user_id: str) -> FicheAnnuaire | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(annuaire_rollee).where(
                    annuaire_rollee.c.tenant_id == str(tenant_id),
                    annuaire_rollee.c.rollee_user_id == rollee_user_id,
                )
            ).first()
        return _fiche(ligne) if ligne is not None else None

    def remplacer(
        self,
        tenant_id: TenantId,
        branchement_id: str,
        fiches: Sequence[FicheAnnuaire],
        partiel: bool = False,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            if not partiel:
                connexion.execute(
                    delete(annuaire_rollee).where(
                        annuaire_rollee.c.tenant_id == str(tenant_id),
                        annuaire_rollee.c.branchement_id == branchement_id,
                    )
                )
            for fiche in fiches:
                valeurs = _valeurs(fiche)
                connexion.execute(
                    insert(annuaire_rollee)
                    .values(**valeurs)
                    .on_conflict_do_update(
                        index_elements=[annuaire_rollee.c.rollee_user_id], set_=valeurs
                    )
                )
