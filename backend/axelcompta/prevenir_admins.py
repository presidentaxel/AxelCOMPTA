"""Prévenir les admins d'un cabinet par mail, via son SMTP par défaut.

AxeLCompta n'a pas de SMTP à lui (décision du 26/09) : le mail part par
l'intégration e-mail du cabinet. Sans SMTP ou sans admin, rien ne part, et
la raison est rendue pour le journal des tâches.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.tenants.branchements import choisir
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.orm import droits_membre
from axelcompta.workflow.rappels_envoi import expediteur_de


def admins(engine: Engine, tenant_id: TenantId) -> list[str]:
    with engine.connect() as connexion:
        return [
            str(email)
            for email in connexion.execute(
                select(droits_membre.c.email).where(
                    droits_membre.c.tenant_id == str(tenant_id), droits_membre.c.role == "admin"
                )
            ).scalars()
        ]


def prevenir_admins(engine: Engine, tenant_id: TenantId, sujet: str, texte: str) -> str:
    """Ce qui s'est passé, en une phrase."""
    smtp = choisir(PostgresBranchements(engine).lister(tenant_id), "mail", None)
    destinataires = admins(engine, tenant_id)
    if smtp is None or not destinataires:
        return "aucun SMTP ou aucun admin : non envoyé"
    try:
        expediteur = expediteur_de(smtp)
        for admin in destinataires:
            expediteur.envoyer(admin, sujet, texte)
    except Exception as exc:  # noqa: BLE001 — l'appelant note l'échec, le passage continue
        return f"envoi en échec : {type(exc).__name__}"
    return f"mail à {len(destinataires)} admin(s)"
