"""Utilisateurs et comptes Rollee en Postgres (AXE-819, migration `c4e9a7d2b5f1`)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .comptes_rollee import CompteRelie, UtilisateurRollee
from .orm import comptes_rollee, utilisateurs_rollee


class PostgresComptesRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def utilisateur(self, dossier_id: DossierId) -> UtilisateurRollee | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(utilisateurs_rollee).where(utilisateurs_rollee.c.dossier_id == dossier_id)
            ).first()
        if ligne is None:
            return None
        return UtilisateurRollee(
            DossierId(ligne.dossier_id), ligne.rollee_user_id, ligne.branchement_id
        )

    def enregistrer_utilisateur(self, utilisateur: UtilisateurRollee, le: datetime) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(utilisateurs_rollee)
                .values(
                    dossier_id=utilisateur.dossier_id,
                    rollee_user_id=utilisateur.rollee_user_id,
                    branchement_id=utilisateur.branchement_id,
                    cree_le=le,
                )
                .on_conflict_do_nothing()
            )

    def comptes(self, dossier_id: DossierId) -> list[CompteRelie]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(comptes_rollee)
                .where(comptes_rollee.c.dossier_id == dossier_id)
                .order_by(comptes_rollee.c.nom)
            ).all()
        return [
            CompteRelie(
                account_id=ligne.account_id,
                dossier_id=DossierId(ligne.dossier_id),
                nom=ligne.nom,
                connecte=ligne.connecte,
                reconnexion=ligne.reconnexion,
                relie_le=ligne.relie_le,
                maj_le=ligne.maj_le,
            )
            for ligne in lignes
        ]

    def remplacer_comptes(self, dossier_id: DossierId, comptes: Sequence[CompteRelie]) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(comptes_rollee).where(comptes_rollee.c.dossier_id == dossier_id)
            )
            if comptes:
                connexion.execute(
                    comptes_rollee.insert(),
                    [
                        {
                            "account_id": c.account_id,
                            "dossier_id": c.dossier_id,
                            "nom": c.nom,
                            "connecte": c.connecte,
                            "reconnexion": c.reconnexion,
                            "relie_le": c.relie_le,
                            "maj_le": c.maj_le,
                        }
                        for c in comptes
                    ],
                )
