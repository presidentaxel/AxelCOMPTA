"""Taux de TVA de l'expert, en Postgres, sous le rôle soumis à la RLS."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import taux_tva_expert as table
from .taux_expert import verifier_taux


class PostgresTauxExpert:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def pour_dossiers(
        self, tenant_id: TenantId, dossier_ids: Sequence[DossierId]
    ) -> dict[DossierId, dict[str, str]]:
        if not dossier_ids:
            return {}
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(table.c.dossier_id, table.c.cle, table.c.taux).where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id.in_(list(dossier_ids)),
                )
            ).all()
        resultat: dict[DossierId, dict[str, str]] = {}
        for dossier_id, cle, taux in lignes:
            resultat.setdefault(DossierId(dossier_id), {})[str(cle)] = str(taux)
        return resultat

    def poser(self, tenant_id: TenantId, dossier_id: DossierId, cle: str, taux: str) -> None:
        verifier_taux(taux)
        requete = (
            pg_insert(table)
            .values(tenant_id=tenant_id, dossier_id=dossier_id, cle=cle, taux=taux)
            .on_conflict_do_update(
                index_elements=["tenant_id", "dossier_id", "cle"],
                set_={"taux": taux},
            )
        )
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(requete)
