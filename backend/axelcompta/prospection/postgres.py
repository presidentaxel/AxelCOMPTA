"""Les demandes d'échange dans Postgres.

Le rôle web (l'API) n'a que le droit d'ajouter une ligne, de compter les
demandes récentes et de noter le résultat de la notification. Lire les noms
et les e-mails est réservé au rôle propriétaire, celui des tâches planifiées.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from axelcompta.prospection.models import DemandeEchange
from axelcompta.prospection.orm import demandes_echange as t


def _depuis_ligne(ligne: Any) -> DemandeEchange:
    return DemandeEchange(
        id=ligne.id,
        nom=ligne.nom,
        email=ligne.email,
        organisation=ligne.organisation,
        role=ligne.role,
        message=ligne.message,
        cree_le=ligne.cree_le,
        notifiee_le=ligne.notifiee_le,
        tentatives=ligne.tentatives,
        derniere_erreur=ligne.derniere_erreur,
    )


class PostgresDemandes:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ajouter(self, demande: DemandeEchange) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                t.insert().values(
                    id=demande.id,
                    nom=demande.nom,
                    email=demande.email,
                    organisation=demande.organisation,
                    role=demande.role,
                    message=demande.message,
                    cree_le=demande.cree_le,
                )
            )

    def email_recu_depuis(self, email: str, depuis: datetime) -> bool:
        with self._engine.connect() as connexion:
            return (
                connexion.execute(
                    select(t.c.id).where(t.c.email == email, t.c.cree_le >= depuis).limit(1)
                ).first()
                is not None
            )

    def nombre_depuis(self, depuis: datetime) -> int:
        with self._engine.connect() as connexion:
            return int(
                connexion.execute(
                    select(func.count()).select_from(t).where(t.c.cree_le >= depuis)
                ).scalar_one()
            )

    def non_notifiees(
        self, avant: datetime, tentatives_max: int, limite: int
    ) -> list[DemandeEchange]:
        requete = (
            select(t)
            .where(
                t.c.notifiee_le.is_(None),
                t.c.tentatives < tentatives_max,
                t.c.cree_le < avant,
            )
            .order_by(t.c.cree_le)
            .limit(limite)
        )
        with self._engine.connect() as connexion:
            return [_depuis_ligne(ligne) for ligne in connexion.execute(requete)]

    def marquer_notifiee(self, id: str, le: datetime) -> None:  # noqa: A002
        with self._engine.begin() as connexion:
            connexion.execute(update(t).where(t.c.id == id).values(notifiee_le=le))

    def noter_echec(self, id: str, raison: str) -> None:  # noqa: A002
        with self._engine.begin() as connexion:
            connexion.execute(
                update(t)
                .where(t.c.id == id)
                .values(tentatives=t.c.tentatives + 1, derniere_erreur=raison)
            )
