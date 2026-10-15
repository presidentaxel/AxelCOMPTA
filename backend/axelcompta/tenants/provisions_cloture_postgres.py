"""Implémentation Postgres de ProvisionsClotureRepository."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from axelcompta.closing.models import ProvisionCloture
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import provisions_cloture as table
from .provisions_cloture import ProvisionsClotureRepository


class PostgresProvisionsClotureRepository(ProvisionsClotureRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(
        self, tenant_id: TenantId, dossier_id: DossierId, annee: int
    ) -> tuple[ProvisionCloture, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table)
                .where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id == dossier_id,
                    table.c.annee == annee,
                )
                .order_by(table.c.position)
            ).all()
        return tuple(
            ProvisionCloture(
                nature=ligne.nature,
                compte_charge=ligne.compte_charge,
                centimes=ligne.centimes,
                libelle=ligne.libelle,
            )
            for ligne in lignes
        )

    def remplacer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        annee: int,
        provisions: tuple[ProvisionCloture, ...],
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(table).where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id == dossier_id,
                    table.c.annee == annee,
                )
            )
            if not provisions:
                return
            connexion.execute(
                table.insert(),
                [
                    {
                        "tenant_id": tenant_id,
                        "dossier_id": dossier_id,
                        "annee": annee,
                        "position": position,
                        "nature": provision.nature,
                        "compte_charge": provision.compte_charge,
                        "centimes": provision.centimes,
                        "libelle": provision.libelle,
                    }
                    for position, provision in enumerate(provisions)
                ],
            )
