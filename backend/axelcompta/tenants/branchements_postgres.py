"""Branchements du portefeuille en Postgres (AXE-872, migration `b8d4e1f7a2c6`)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .branchements import Branchement
from .orm import branchements, branchements_dossier


class PostgresBranchements:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, tenant_id: TenantId) -> list[Branchement]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(branchements)
                .where(branchements.c.tenant_id == tenant_id)
                .order_by(branchements.c.type, branchements.c.nom)
            ).all()
        return [
            Branchement(
                id=ligne.id,
                tenant_id=TenantId(ligne.tenant_id),
                type=ligne.type,
                fournisseur=ligne.fournisseur,
                nom=ligne.nom,
                parametres_chiffres=ligne.parametres_chiffres,
                par_defaut=ligne.par_defaut,
                actif=ligne.actif,
                maj_le=ligne.maj_le,
            )
            for ligne in lignes
        ]

    def enregistrer(self, a_enregistrer: Sequence[Branchement], par: str, le: datetime) -> None:
        # Ceux qui perdent le défaut d'abord : l'index unique sur le défaut
        # refuserait deux défauts, même un instant.
        ordre = sorted(a_enregistrer, key=lambda b: b.par_defaut)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for branchement in ordre:
                valeurs = {
                    "nom": branchement.nom,
                    "parametres_chiffres": branchement.parametres_chiffres,
                    "par_defaut": branchement.par_defaut,
                    "actif": branchement.actif,
                    "maj_par": par,
                    "maj_le": le,
                }
                connexion.execute(
                    insert(branchements)
                    .values(
                        id=branchement.id,
                        tenant_id=branchement.tenant_id,
                        type=branchement.type,
                        fournisseur=branchement.fournisseur,
                        **valeurs,
                    )
                    .on_conflict_do_update(index_elements=[branchements.c.id], set_=valeurs)
                )

    def choix_du_dossier(self, tenant_id: TenantId, dossier_id: DossierId) -> dict[str, str]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(branchements_dossier.c.type, branchements_dossier.c.branchement_id).where(
                    branchements_dossier.c.tenant_id == tenant_id,
                    branchements_dossier.c.dossier_id == dossier_id,
                )
            ).all()
        return {ligne.type: ligne.branchement_id for ligne in lignes}

    def choisir_pour_dossier(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        type_: str,
        branchement_id: str | None,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            if branchement_id is None:
                connexion.execute(
                    delete(branchements_dossier).where(
                        branchements_dossier.c.tenant_id == tenant_id,
                        branchements_dossier.c.dossier_id == dossier_id,
                        branchements_dossier.c.type == type_,
                    )
                )
                return
            connexion.execute(
                insert(branchements_dossier)
                .values(
                    dossier_id=dossier_id,
                    type=type_,
                    tenant_id=tenant_id,
                    branchement_id=branchement_id,
                )
                .on_conflict_do_update(
                    index_elements=[branchements_dossier.c.dossier_id, branchements_dossier.c.type],
                    set_={"branchement_id": branchement_id},
                )
            )


def branchement_pour_webhook(engine: Engine, branchement_id: str) -> tuple[TenantId, str] | None:
    """AXE-820 : la route publique d'un webhook Rollee, sans identité, ne lit
    que le portefeuille et les paramètres chiffrés d'un branchement Rollee
    actif (fonction `axelcompta_webhook_rollee`, migration `d6b2f8a4c3e7`)."""
    with engine.connect() as connexion:
        ligne = connexion.execute(
            text("SELECT * FROM axelcompta_webhook_rollee(:b)"), {"b": branchement_id}
        ).first()
    if ligne is None:
        return None
    return TenantId(ligne.tenant_id), str(ligne.parametres_chiffres)


def branchement_par_id(engine: Engine, branchement_id: str) -> Branchement | None:
    """Rôle propriétaire (scripts d'administration) : un branchement par son
    identifiant, quel que soit son portefeuille."""
    with engine.connect() as connexion:
        tenant_id = connexion.execute(
            select(branchements.c.tenant_id).where(branchements.c.id == branchement_id)
        ).scalar()
    if tenant_id is None:
        return None
    lus = PostgresBranchements(engine).lister(TenantId(tenant_id))
    return next((b for b in lus if b.id == branchement_id), None)
