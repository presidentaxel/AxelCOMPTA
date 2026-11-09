"""Habilitations, engagements et décisions d'expert en Postgres (AXE-800,
migration `c9f3a1e6d248`). Une décision s'écrit avec ses écritures, dans une
seule transaction (`inserer_ecriture` garde les contrôles I1 et I4)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine, Row

from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.core.rls import appliquer_rls
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import inserer_ecriture

from .expert_comptable import DecisionExpert, Engagement, Habilitation
from .orm import decisions_expert, engagements_expert, habilitations_expert


class PostgresExpertRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def habilitation(self, tenant_id: TenantId, email: str) -> Habilitation | None:
        ligne = self._derniere(habilitations_expert, "accordee_le", tenant_id, email)
        return None if ligne is None else _habilitation(ligne)

    def habiliter(self, habilitation: Habilitation) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                habilitations_expert.insert().values(
                    id=str(uuid.uuid4()),
                    tenant_id=habilitation.tenant_id,
                    email=habilitation.email.lower(),
                    nom=habilitation.nom,
                    cabinet=habilitation.cabinet,
                    numero_ordre=habilitation.numero_ordre,
                    lettre_mission=habilitation.lettre_mission,
                    date_lettre=habilitation.date_lettre,
                    dossiers=list(habilitation.dossiers),
                    accordee_par=habilitation.accordee_par,
                    accordee_le=habilitation.accordee_le,
                )
            )

    def engagement(self, tenant_id: TenantId, email: str) -> Engagement | None:
        ligne = self._derniere(engagements_expert, "accepte_le", tenant_id, email)
        return None if ligne is None else _engagement(ligne)

    def accepter(self, engagement: Engagement) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                engagements_expert.insert().values(
                    id=str(uuid.uuid4()),
                    tenant_id=engagement.tenant_id,
                    email=engagement.email.lower(),
                    version=engagement.version,
                    texte=engagement.texte,
                    adresse=engagement.adresse,
                    acteur=engagement.acteur,
                    accepte_le=engagement.accepte_le,
                )
            )

    def decider(self, decision: DecisionExpert, ecritures: Sequence[Ecriture]) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for ecriture in ecritures:
                inserer_ecriture(connexion, ecriture)
            connexion.execute(
                decisions_expert.insert().values(
                    id=decision.id,
                    tenant_id=decision.tenant_id,
                    dossier_id=decision.dossier_id,
                    ecriture_id=decision.ecriture_id,
                    nature=decision.nature,
                    motif=decision.motif,
                    auteur=decision.auteur,
                    auteur_nom=decision.auteur_nom,
                    version_engagement=decision.version_engagement,
                    decide_le=decision.le,
                    ecritures=[str(e.id) for e in ecritures],
                )
            )

    def decisions(self, dossier_id: DossierId) -> tuple[DecisionExpert, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(decisions_expert)
                .where(decisions_expert.c.dossier_id == dossier_id)
                .order_by(decisions_expert.c.decide_le)
            ).all()
        return tuple(_decision(ligne) for ligne in lignes)

    def _derniere(
        self, table: Any, colonne_date: str, tenant_id: TenantId, email: str
    ) -> Row[Any] | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return connexion.execute(
                select(table)
                .where(table.c.tenant_id == tenant_id, table.c.email == email.lower())
                .order_by(table.c[colonne_date].desc())
                .limit(1)
            ).first()


def _habilitation(ligne: Row[Any]) -> Habilitation:
    return Habilitation(
        tenant_id=TenantId(ligne.tenant_id),
        email=ligne.email,
        nom=ligne.nom,
        cabinet=ligne.cabinet,
        numero_ordre=ligne.numero_ordre,
        lettre_mission=ligne.lettre_mission,
        date_lettre=ligne.date_lettre,
        dossiers=tuple(DossierId(d) for d in ligne.dossiers),
        accordee_par=UserId(ligne.accordee_par),
        accordee_le=ligne.accordee_le,
    )


def _engagement(ligne: Row[Any]) -> Engagement:
    return Engagement(
        tenant_id=TenantId(ligne.tenant_id),
        email=ligne.email,
        version=ligne.version,
        texte=ligne.texte,
        adresse=ligne.adresse,
        acteur=UserId(ligne.acteur),
        accepte_le=ligne.accepte_le,
    )


def _decision(ligne: Row[Any]) -> DecisionExpert:
    return DecisionExpert(
        id=ligne.id,
        tenant_id=TenantId(ligne.tenant_id),
        dossier_id=DossierId(ligne.dossier_id),
        ecriture_id=EcritureId(ligne.ecriture_id) if ligne.ecriture_id else None,
        nature=ligne.nature,
        motif=ligne.motif,
        auteur=UserId(ligne.auteur),
        auteur_nom=ligne.auteur_nom,
        version_engagement=ligne.version_engagement,
        le=ligne.decide_le,
        ecritures=tuple(EcritureId(e) for e in ligne.ecritures),
    )
