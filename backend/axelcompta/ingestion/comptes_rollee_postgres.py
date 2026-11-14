"""Utilisateurs et comptes Rollee en Postgres (AXE-819, migration `c4e9a7d2b5f1`)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId
from axelcompta.core.rls import appliquer_rls

from .comptes_rollee import CompteRelie, UtilisateurRollee
from .orm import comptes_rollee, utilisateurs_rollee


class PostgresComptesRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def utilisateurs(self, dossier_id: DossierId) -> list[UtilisateurRollee]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(utilisateurs_rollee)
                .where(utilisateurs_rollee.c.dossier_id == dossier_id)
                .order_by(utilisateurs_rollee.c.cree_le, utilisateurs_rollee.c.rollee_user_id)
            ).all()
        return [
            UtilisateurRollee(
                DossierId(ligne.dossier_id), ligne.rollee_user_id, ligne.branchement_id
            )
            for ligne in lignes
        ]

    def utilisateur(self, dossier_id: DossierId) -> UtilisateurRollee | None:
        trouves = self.utilisateurs(dossier_id)
        return trouves[0] if trouves else None

    def dossier_du_user(self, rollee_user_id: str) -> DossierId | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            dossier_id = connexion.execute(
                select(utilisateurs_rollee.c.dossier_id).where(
                    utilisateurs_rollee.c.rollee_user_id == rollee_user_id
                )
            ).scalar()
        return DossierId(dossier_id) if dossier_id else None

    def dossiers_relies(self) -> list[DossierId]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(utilisateurs_rollee.c.dossier_id)
                .distinct()
                .order_by(utilisateurs_rollee.c.dossier_id)
            ).scalars()
            return [DossierId(d) for d in lignes]

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
                rollee_user_id=ligne.rollee_user_id,
            )
            for ligne in lignes
        ]

    def remplacer_comptes(
        self,
        dossier_id: DossierId,
        comptes: Sequence[CompteRelie],
        rollee_user_id: str | None = None,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            requete = delete(comptes_rollee).where(comptes_rollee.c.dossier_id == dossier_id)
            if rollee_user_id is not None:
                ids = [c.account_id for c in comptes]
                bornes = [comptes_rollee.c.rollee_user_id == rollee_user_id]
                if ids:
                    bornes.append(comptes_rollee.c.account_id.in_(ids))
                requete = requete.where(or_(*bornes))
            connexion.execute(requete)
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
                            "rollee_user_id": c.rollee_user_id,
                        }
                        for c in comptes
                    ],
                )

    def retirer_comptes_sans_user(self, dossier_id: DossierId) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(comptes_rollee).where(
                    comptes_rollee.c.dossier_id == dossier_id,
                    comptes_rollee.c.rollee_user_id.is_(None),
                )
            )
