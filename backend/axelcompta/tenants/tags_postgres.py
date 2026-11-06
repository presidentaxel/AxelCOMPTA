"""Tags en Postgres (AXE-829). Poses, retraits et réglages sont des
événements append-only (verrou en base) : l'état courant est le dernier."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine

from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.core.rls import appliquer_rls

from .orm import evenements_tags, reglages_exclusion, tags
from .tags import TAGS_PROPOSES, Tag, TagInvalide, exclusions_completes, verifier_traitement


class PostgresTagsRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister_tags(self, tenant_id: TenantId) -> tuple[Tag, ...]:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            self._assurer_proposes(connexion, tenant_id)
            lignes = connexion.execute(
                select(tags).where(tags.c.tenant_id == tenant_id).order_by(tags.c.nom)
            ).all()
        return tuple(
            Tag(TenantId(ligne.tenant_id), ligne.nom, ligne.description) for ligne in lignes
        )

    def creer_tag(self, tag: Tag) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(tags)
                .values(
                    tenant_id=tag.tenant_id,
                    nom=tag.nom,
                    description=tag.description,
                    cree_le=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
            )

    def tags_des_dossiers(self, tenant_id: TenantId) -> dict[DossierId, frozenset[str]]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return self._etat(connexion, tenant_id)

    def poser(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            self._assurer_proposes(connexion, tenant_id)
            existe = connexion.execute(
                select(tags.c.nom).where(tags.c.tenant_id == tenant_id, tags.c.nom == tag)
            ).first()
            if existe is None:
                raise TagInvalide(f"Tag inconnu dans ce portefeuille : {tag}.")
            if tag not in self._etat(connexion, tenant_id).get(dossier_id, frozenset()):
                self._noter(connexion, tenant_id, dossier_id, tag, True, par, le)

    def retirer(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            if tag in self._etat(connexion, tenant_id).get(dossier_id, frozenset()):
                self._noter(connexion, tenant_id, dossier_id, tag, False, par, le)

    def exclusions(self, tenant_id: TenantId) -> dict[str, frozenset[str]]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(reglages_exclusion.c.traitement, reglages_exclusion.c.tags)
                .where(reglages_exclusion.c.tenant_id == tenant_id)
                .order_by(reglages_exclusion.c.rang)
            ).all()
        derniers = {traitement: frozenset(valeur) for traitement, valeur in lignes}
        return exclusions_completes(derniers)

    def regler_exclusion(
        self,
        tenant_id: TenantId,
        traitement: str,
        tags_exclus: frozenset[str],
        par: UserId,
        le: datetime,
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                reglages_exclusion.insert().values(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    traitement=verifier_traitement(traitement),
                    tags=sorted(tags_exclus),
                    par=par,
                    le=le,
                )
            )

    @staticmethod
    def _assurer_proposes(connexion: Connection, tenant_id: TenantId) -> None:
        maintenant = datetime.now(UTC)
        for nom, description in TAGS_PROPOSES.items():
            connexion.execute(
                insert(tags)
                .values(tenant_id=tenant_id, nom=nom, description=description, cree_le=maintenant)
                .on_conflict_do_nothing()
            )

    @staticmethod
    def _etat(connexion: Connection, tenant_id: TenantId) -> dict[DossierId, frozenset[str]]:
        lignes = connexion.execute(
            select(evenements_tags.c.dossier_id, evenements_tags.c.tag, evenements_tags.c.pose)
            .where(evenements_tags.c.tenant_id == tenant_id)
            .order_by(evenements_tags.c.rang)
        ).all()
        etat: dict[tuple[str, str], bool] = {}
        for dossier_id, tag, pose in lignes:
            etat[(dossier_id, tag)] = pose
        par_dossier: dict[DossierId, set[str]] = {}
        for (dossier_id, tag), pose in etat.items():
            if pose:
                par_dossier.setdefault(DossierId(dossier_id), set()).add(tag)
        return {d: frozenset(t) for d, t in par_dossier.items()}

    @staticmethod
    def _noter(
        connexion: Connection,
        tenant_id: TenantId,
        dossier_id: DossierId,
        tag: str,
        pose: bool,
        par: UserId,
        le: datetime,
    ) -> None:
        connexion.execute(
            evenements_tags.insert().values(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                dossier_id=dossier_id,
                tag=tag,
                pose=pose,
                par=par,
                le=le,
            )
        )
