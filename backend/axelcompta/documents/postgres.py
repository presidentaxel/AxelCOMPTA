"""Justificatifs en Postgres, lus et écrits sous le rôle soumis à la RLS."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import justificatifs as table
from .preparer import preparer


class PostgresJustificatifRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        contenu: bytes,
        extension: str,
    ) -> None:
        justificatif = preparer(tenant_id, dossier_id, ecriture_id, contenu, extension)
        valeurs = {
            "tenant_id": justificatif.tenant_id,
            "dossier_id": justificatif.dossier_id,
            "ecriture_id": justificatif.ecriture_id,
            "empreinte": justificatif.empreinte,
            "extension": justificatif.extension,
            "taille_octets": justificatif.taille_octets,
            "contenu": contenu,
        }
        requete = (
            pg_insert(table)
            .values(valeurs)
            .on_conflict_do_update(
                index_elements=["tenant_id", "dossier_id", "ecriture_id"],
                set_={
                    "empreinte": justificatif.empreinte,
                    "extension": justificatif.extension,
                    "taille_octets": justificatif.taille_octets,
                    "contenu": contenu,
                },
            )
        )
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(requete)

    def a_un_justificatif(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bool:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(table.c.ecriture_id)
                .where(
                    table.c.tenant_id == tenant_id,
                    table.c.dossier_id == dossier_id,
                    table.c.ecriture_id == ecriture_id,
                )
                .limit(1)
            ).first()
        return ligne is not None
