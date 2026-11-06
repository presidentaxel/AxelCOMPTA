"""Contacts proposés et décisions, en Postgres (AXE-845)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from axelcompta.core.ids import TenantId
from axelcompta.core.rls import appliquer_rls

from .contacts_proposes import DecisionContact, PropositionStockee
from .orm import contacts_proposes, decisions_contacts


class PostgresContactsProposes:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def remplacer_propositions(
        self, tenant_id: TenantId, propositions: list[PropositionStockee]
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(contacts_proposes).where(contacts_proposes.c.tenant_id == tenant_id)
            )
            if propositions:
                connexion.execute(
                    contacts_proposes.insert(),
                    [
                        {
                            "tenant_id": tenant_id,
                            "contact_nr": p.contact_nr,
                            "nom": p.nom,
                            "siren": p.siren,
                            "forme": p.forme,
                            "exercice_debut": p.exercice_debut,
                            "code_naf": p.code_naf,
                            "avertissements": list(p.avertissements),
                            "cessee": p.cessee,
                            "detecte_le": p.detecte_le,
                        }
                        for p in propositions
                    ],
                )

    def propositions(self, tenant_id: TenantId) -> list[PropositionStockee]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(contacts_proposes)
                .where(contacts_proposes.c.tenant_id == tenant_id)
                .order_by(contacts_proposes.c.contact_nr)
            ).all()
        return [
            PropositionStockee(
                ligne.contact_nr,
                ligne.nom,
                ligne.siren,
                ligne.forme,
                ligne.exercice_debut,
                ligne.code_naf,
                tuple(ligne.avertissements),
                ligne.cessee,
                ligne.detecte_le,
            )
            for ligne in lignes
        ]

    def decider(
        self,
        tenant_id: TenantId,
        contact_nr: str,
        decision: DecisionContact,
        par: str,
        le: datetime,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                decisions_contacts.insert().values(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    contact_nr=contact_nr,
                    decision=decision,
                    par=par,
                    le=le,
                )
            )

    def decisions(self, tenant_id: TenantId) -> dict[str, DecisionContact]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(decisions_contacts.c.contact_nr, decisions_contacts.c.decision)
                .where(decisions_contacts.c.tenant_id == tenant_id)
                .order_by(decisions_contacts.c.rang)
            ).all()
        resultat: dict[str, DecisionContact] = {}
        for numero, decision in lignes:
            if decision in ("ajouter", "ignorer", "reprendre"):
                resultat[numero] = decision
        return resultat
