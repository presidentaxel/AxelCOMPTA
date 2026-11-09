"""Qualifications d'alertes en Postgres (AXE-814). Une instruction lit
l'état courant et ajoute l'événement dans la même transaction, sous un
verrou par alerte : deux qualifications simultanées ne sautent pas le cycle."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection, Engine

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .instruction import EvenementInstruction, etat_actuel, transition
from .orm import qualifications_anomalie as table


class PostgresInstructions:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def etats(self, dossier_id: DossierId) -> dict[str, str]:
        dernier = (
            select(table.c.alerte_id, func.max(table.c.rang).label("rang"))
            .where(table.c.dossier_id == dossier_id)
            .group_by(table.c.alerte_id)
            .subquery()
        )
        requete = select(table.c.alerte_id, table.c.etat).join(
            dernier, (table.c.alerte_id == dernier.c.alerte_id) & (table.c.rang == dernier.c.rang)
        )
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return {alerte_id: etat for alerte_id, etat in connexion.execute(requete)}

    def historique(self, dossier_id: DossierId, alerte_id: str) -> tuple[EvenementInstruction, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return _historique(connexion, dossier_id, alerte_id)

    def instruire(
        self,
        dossier_id: DossierId,
        alerte_id: str,
        decision: str,
        acteur: str,
        commentaire: str,
        le: datetime,
    ) -> str:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:cle))"),
                {"cle": f"{dossier_id}:{alerte_id}"},
            )
            courant = etat_actuel(_historique(connexion, dossier_id, alerte_id))
            suivant = transition(courant, decision, commentaire)
            connexion.execute(
                table.insert().values(
                    id=str(uuid.uuid4()),
                    dossier_id=dossier_id,
                    alerte_id=alerte_id,
                    etat=suivant,
                    commentaire=commentaire.strip(),
                    acteur=acteur,
                    le=le,
                )
            )
        return suivant


def _historique(
    connexion: Connection, dossier_id: DossierId, alerte_id: str
) -> tuple[EvenementInstruction, ...]:
    lignes = connexion.execute(
        select(table.c.alerte_id, table.c.etat, table.c.acteur, table.c.commentaire, table.c.le)
        .where(table.c.dossier_id == dossier_id, table.c.alerte_id == alerte_id)
        .order_by(table.c.rang)
    ).all()
    return tuple(EvenementInstruction(*ligne) for ligne in lignes)
