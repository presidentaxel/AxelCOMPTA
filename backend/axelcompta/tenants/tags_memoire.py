"""Tags en mémoire (tests et démo) — même contrat que `tags_postgres.py`."""

from __future__ import annotations

from datetime import datetime

from axelcompta.core.ids import DossierId, TenantId, UserId

from .tags import TAGS_PROPOSES, Tag, TagInvalide, exclusions_completes, verifier_traitement


class TagsMemoire:
    def __init__(self) -> None:
        self._tags: dict[tuple[TenantId, str], Tag] = {}
        # Événements dans l'ordre : (tenant, dossier, tag, posé ?)
        self._evenements: list[tuple[TenantId, DossierId, str, bool]] = []
        self._reglages: dict[tuple[TenantId, str], frozenset[str]] = {}

    def lister_tags(self, tenant_id: TenantId) -> tuple[Tag, ...]:
        for nom, description in TAGS_PROPOSES.items():
            self._tags.setdefault((tenant_id, nom), Tag(tenant_id, nom, description))
        return tuple(
            sorted(
                (t for (tid, _), t in self._tags.items() if tid == tenant_id), key=lambda t: t.nom
            )
        )

    def creer_tag(self, tag: Tag) -> None:
        self._tags.setdefault((tag.tenant_id, tag.nom), tag)

    def tags_des_dossiers(self, tenant_id: TenantId) -> dict[DossierId, frozenset[str]]:
        etat: dict[tuple[DossierId, str], bool] = {}
        for tid, dossier_id, tag, pose in self._evenements:
            if tid == tenant_id:
                etat[(dossier_id, tag)] = pose
        par_dossier: dict[DossierId, set[str]] = {}
        for (dossier_id, tag), pose in etat.items():
            if pose:
                par_dossier.setdefault(dossier_id, set()).add(tag)
        return {d: frozenset(t) for d, t in par_dossier.items()}

    def poser(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None:
        if tag not in {t.nom for t in self.lister_tags(tenant_id)}:
            raise TagInvalide(f"Tag inconnu dans ce portefeuille : {tag}.")
        if tag not in self.tags_des_dossiers(tenant_id).get(dossier_id, frozenset()):
            self._evenements.append((tenant_id, dossier_id, tag, True))

    def retirer(
        self, tenant_id: TenantId, dossier_id: DossierId, tag: str, par: UserId, le: datetime
    ) -> None:
        if tag in self.tags_des_dossiers(tenant_id).get(dossier_id, frozenset()):
            self._evenements.append((tenant_id, dossier_id, tag, False))

    def exclusions(self, tenant_id: TenantId) -> dict[str, frozenset[str]]:
        return exclusions_completes(
            {
                traitement: tags
                for (tid, traitement), tags in self._reglages.items()
                if tid == tenant_id
            }
        )

    def regler_exclusion(
        self,
        tenant_id: TenantId,
        traitement: str,
        tags: frozenset[str],
        par: UserId,
        le: datetime,
    ) -> None:
        self._reglages[(tenant_id, verifier_traitement(traitement))] = frozenset(tags)
