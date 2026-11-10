"""Rappels automatiques et envoi des rappels (AXE-808).

Composition root comme `notifier.py` (doc 18). Lancé par les tâches
planifiées (`axelcompta.taches`) chaque heure, et par le worker dès qu'un
gestionnaire déclenche un rappel. Rôle propriétaire : traite tous les
portefeuilles.

1. Règles automatiques (`avant_cloture`, `a_traiter`) : crée les rappels
   dus, une seule fois par raison (`workflow/rappels_auto.py`).
2. Envoi : chaque envoi en attente est tenté une fois ; trois essais, puis
   « échec » (`workflow/rappels_envoi.py`).
"""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_comptes import SupabaseCompteRepository, SupabaseConfig
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.orm import rappels, regles_rappel
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.notifications import ecritures_a_trancher
from axelcompta.workflow.rappels_auto import Regle, rappels_a_creer
from axelcompta.workflow.rappels_envoi import (
    Contexte,
    envois_du_rappel,
    envoyer_en_attente,
    expediteur_de,
)
from axelcompta.workflow.rappels_envoi_postgres import PostgresEnvois

VARIABLE_URL_APP = "AXELCOMPTA_URL_APP"


def _regles(engine: Engine, tenant_id: str) -> list[Regle]:
    with engine.connect() as connexion:
        lignes = connexion.execute(
            select(regles_rappel).where(regles_rappel.c.tenant_id == tenant_id)
        ).all()
    return [
        Regle(
            id=ligne.id,
            message=ligne.message,
            canaux=tuple(ligne.canaux),
            portee=ligne.portee,
            dossier_ids=tuple(ligne.dossier_ids or ()),
            declencheur=ligne.declencheur,
            jours=ligne.jours_avant,
            actif=bool(ligne.actif),
        )
        for ligne in lignes
    ]


def _deja(engine: Engine, tenant_id: str) -> dict[tuple[str, str], list[datetime]]:
    with engine.connect() as connexion:
        lignes = connexion.execute(
            select(rappels.c.regle_id, rappels.c.dossier_id, rappels.c.cree_le).where(
                rappels.c.tenant_id == tenant_id
            )
        ).all()
    deja: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for regle_id, dossier_id, cree_le in lignes:
        if regle_id and dossier_id:
            deja[(regle_id, dossier_id)].append(cree_le)
    return deja


def planifier(engine: Engine, maintenant: datetime) -> int:
    """Crée les rappels automatiques dus, et leurs envois. Renvoie leur nombre."""
    depot_dossiers, envois = PostgresDossierRepository(engine), PostgresEnvois(engine)
    ledger, decisions = PostgresLedgerService(engine), PostgresDecisionRepository(engine)
    crees = 0
    for tenant in depot_dossiers.lister_tenants():
        regles = _regles(engine, tenant.id)
        if not any(r.actif and r.declencheur != "manuel" for r in regles):
            continue
        dossiers = depot_dossiers.lister_par_tenant(tenant.id)
        a_traiter = {}
        for dossier in dossiers:
            dates = {e.id: e.date for e in ledger.grand_livre(dossier.id)}
            en_attente = [dates[i] for i in ecritures_a_trancher(ledger, decisions, dossier.id)]
            if en_attente:
                a_traiter[dossier.id] = min(en_attente)
        branches = list(envois.canaux_branches(tenant.id))
        for rappel in rappels_a_creer(
            regles, dossiers, _deja(engine, tenant.id), a_traiter, maintenant.date()
        ):
            _enregistrer(
                engine,
                envois,
                tenant.id,
                rappel.regle_id,
                rappel.dossier_id,
                rappel.message,
                rappel.canaux,
                branches,
                maintenant,
            )
            crees += 1
    return crees


def _enregistrer(
    engine: Engine,
    envois: PostgresEnvois,
    tenant_id: TenantId,
    regle_id: str,
    dossier_id: DossierId,
    message: str,
    canaux: tuple[str, ...],
    branches: list[str],
    maintenant: datetime,
) -> None:
    rappel_id = str(uuid.uuid4())
    with engine.begin() as connexion:
        connexion.execute(
            rappels.insert().values(
                id=rappel_id,
                tenant_id=tenant_id,
                dossier_id=dossier_id,
                regle_id=regle_id,
                message=message,
                canal=",".join(canaux),
                cree_le=maintenant,
            )
        )
    envois.creer(
        envois_du_rappel(rappel_id, tenant_id, dossier_id, message, canaux, branches, maintenant)
    )


def envoyer(engine: Engine, maintenant: datetime) -> dict[str, int]:
    """Une passe d'envoi. L'e-mail du chauffeur vient de son compte."""
    comptes = SupabaseCompteRepository(SupabaseConfig.depuis_env())
    ledger, decisions = PostgresLedgerService(engine), PostgresDecisionRepository(engine)

    def destinataire(dossier_id: DossierId, canal: str) -> str | None:
        if canal != "mail":
            return None  # aucun numéro de chauffeur n'est connu aujourd'hui
        invitation = comptes.statut(dossier_id)
        return invitation.email if invitation else None

    contexte = Contexte(
        destinataire=destinataire,
        nb_a_traiter=lambda d: len(ecritures_a_trancher(ledger, decisions, d)),
        base_url=os.environ.get(VARIABLE_URL_APP, "http://localhost:3000").rstrip("/"),
    )
    return envoyer_en_attente(PostgresEnvois(engine), contexte, expediteur_de, maintenant)
