"""Envois de rappel et désinscriptions en Postgres (AXE-808, migration
`e6b2d9f4a371`). Les intégrations sont des branchements du portefeuille
(`tenants.branchements_postgres`, AXE-872)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .orm import desinscriptions, envois_rappel
from .rappels_envoi import EnvoiRappel


class PostgresEnvois:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def creer(self, envois: Sequence[EnvoiRappel]) -> None:
        if not envois:
            return
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                envois_rappel.insert(),
                [
                    {
                        "id": e.id,
                        "rappel_id": e.rappel_id,
                        "tenant_id": e.tenant_id,
                        "dossier_id": e.dossier_id,
                        "canal": e.canal,
                        "message": e.message,
                        "statut": e.statut,
                        "tentatives": e.tentatives,
                        "raison": e.raison,
                        "maj_le": e.maj_le,
                        "branchement_id": e.branchement_id,
                    }
                    for e in envois
                ],
            )

    def en_attente(self, limite: int) -> list[EnvoiRappel]:
        with self._engine.connect() as connexion:
            lignes = connexion.execute(
                select(envois_rappel)
                .where(envois_rappel.c.statut == "en_attente")
                .order_by(envois_rappel.c.maj_le)
                .limit(limite)
            ).all()
        return [_envoi(ligne) for ligne in lignes]

    def enregistrer(self, envoi: EnvoiRappel) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                update(envois_rappel)
                .where(envois_rappel.c.id == envoi.id)
                .values(
                    statut=envoi.statut,
                    tentatives=envoi.tentatives,
                    raison=envoi.raison,
                    maj_le=envoi.maj_le,
                    branchement_id=envoi.branchement_id,
                )
            )

    def desinscrits(self, dossier_ids: Sequence[DossierId]) -> set[tuple[str, str]]:
        if not dossier_ids:
            return set()
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(desinscriptions.c.dossier_id, desinscriptions.c.canal).where(
                    desinscriptions.c.dossier_id.in_(list(dossier_ids))
                )
            ).all()
        return {(ligne.dossier_id, ligne.canal) for ligne in lignes}

    def desinscrire(self, dossier_id: DossierId, canal: str) -> None:
        """Par la fonction `axelcompta_desinscrire` : le lien est public."""
        with self._engine.begin() as connexion:
            connexion.execute(
                text("SELECT axelcompta_desinscrire(:d, :c)"), {"d": dossier_id, "c": canal}
            )

    def du_dossier(self, dossier_id: DossierId, limite: int) -> list[EnvoiRappel]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(envois_rappel)
                .where(envois_rappel.c.dossier_id == dossier_id)
                .order_by(envois_rappel.c.maj_le.desc())
                .limit(limite)
            ).all()
        return [_envoi(ligne) for ligne in lignes]


def _envoi(ligne: Row[Any]) -> EnvoiRappel:
    return EnvoiRappel(
        id=ligne.id,
        rappel_id=ligne.rappel_id,
        tenant_id=TenantId(ligne.tenant_id),
        dossier_id=DossierId(ligne.dossier_id),
        canal=ligne.canal,
        message=ligne.message,
        statut=ligne.statut,
        tentatives=ligne.tentatives,
        raison=ligne.raison,
        maj_le=ligne.maj_le,
        branchement_id=ligne.branchement_id,
    )
