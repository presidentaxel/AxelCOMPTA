"""Implémentation Postgres de DossierRepository (seul fichier de `tenants`
qui fait de l'I/O)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .identite_json import identite_depuis_json, identite_vers_json
from .models import Dossier, Tenant, verifier_mode_relance
from .orm import dossiers, tenants
from .repository import DossierRepository
from .statuts import configuration_de


class PostgresDossierRepository(DossierRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer_tenant(self, tenant: Tenant) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(tenants)
                .values(
                    id=tenant.id,
                    nom=tenant.nom,
                    relance_consentement=tenant.relance_consentement,
                )
                .on_conflict_do_nothing()
            )

    def enregistrer(self, dossier: Dossier) -> None:
        configuration_de(dossier)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(dossiers)
                .values(
                    id=dossier.id,
                    tenant_id=dossier.tenant_id,
                    forme_juridique=dossier.forme_juridique,
                    regime_imposition=dossier.regime_imposition,
                    regime_tva=dossier.regime_tva,
                    nom=dossier.nom,
                    tva_recettes_regime=dossier.tva_recettes_regime,
                    exercice_debut=dossier.exercice_debut,
                    plateformes=list(dossier.plateformes),
                    mode_acces_bancaire=dossier.mode_acces_bancaire,
                    contact_nr=dossier.contact_nr,
                    exercice_fin=dossier.exercice_fin,
                    identite=identite_vers_json(dossier.identite),
                    retire_le=dossier.retire_le,
                    pack_metier=dossier.pack_metier,
                    option_ir_debut=dossier.option_ir_debut,
                    relance_consentement=dossier.relance_consentement,
                    code_naf=dossier.code_naf,
                    a_confirmer=list(dossier.a_confirmer),
                )
                .on_conflict_do_nothing(index_elements=[dossiers.c.id])
            )

    def obtenir(self, dossier_id: DossierId) -> Dossier | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(select(dossiers).where(dossiers.c.id == dossier_id)).first()
        return _vers_dossier(ligne) if ligne is not None else None

    def lister_par_tenant(self, tenant_id: TenantId) -> tuple[Dossier, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(dossiers)
                .where(dossiers.c.tenant_id == tenant_id, dossiers.c.retire_le.is_(None))
                .order_by(dossiers.c.id)
            ).all()
        return tuple(_vers_dossier(ligne) for ligne in lignes)

    def obtenir_tenant(self, tenant_id: TenantId) -> Tenant | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(select(tenants).where(tenants.c.id == tenant_id)).first()
        if ligne is None:
            return None
        return _vers_tenant(ligne)

    def poser_forme_juridique(self, dossier_id: DossierId, forme: str) -> None:
        dossier = self.obtenir(dossier_id)
        if dossier is None:
            raise ValueError(f"dossier inconnu : {dossier_id}")
        configuration_de(replace(dossier, forme_juridique=forme))
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers).where(dossiers.c.id == dossier_id).values(forme_juridique=forme)
            )

    def reconfigurer_depuis_sirene(self, dossier: Dossier) -> None:
        configuration_de(dossier)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers)
                .where(dossiers.c.id == dossier.id)
                .values(
                    forme_juridique=dossier.forme_juridique,
                    exercice_debut=dossier.exercice_debut,
                    exercice_fin=dossier.exercice_fin,
                    code_naf=dossier.code_naf,
                    a_confirmer=list(dossier.a_confirmer),
                )
            )

    def ouvrir_exercice(self, dossier: Dossier) -> None:
        configuration_de(dossier)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers)
                .where(dossiers.c.id == dossier.id)
                .values(
                    exercice_debut=dossier.exercice_debut,
                    exercice_fin=dossier.exercice_fin,
                    regime_imposition=dossier.regime_imposition,
                    option_ir_debut=dossier.option_ir_debut,
                    regime_tva=dossier.regime_tva,
                    tva_recettes_regime=dossier.tva_recettes_regime,
                )
            )

    def lister_tenants(self) -> tuple[Tenant, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(select(tenants).order_by(tenants.c.id)).all()
        return tuple(_vers_tenant(ligne) for ligne in lignes)

    def renommer_tenant(self, tenant_id: TenantId, nom: str) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(update(tenants).where(tenants.c.id == tenant_id).values(nom=nom))

    def regler_relance_tenant(self, tenant_id: TenantId, mode: str) -> None:
        verifier_mode_relance(mode)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(tenants).where(tenants.c.id == tenant_id).values(relance_consentement=mode)
            )

    def regler_relance_dossier(self, dossier_id: DossierId, mode: str | None) -> None:
        if mode is not None:
            verifier_mode_relance(mode)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers)
                .where(dossiers.c.id == dossier_id)
                .values(relance_consentement=mode)
            )

    def retirer(self, dossier_id: DossierId) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers).where(dossiers.c.id == dossier_id).values(retire_le=date.today())
            )

    def lister_retires(self, tenant_id: TenantId) -> tuple[Dossier, ...]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(dossiers)
                .where(dossiers.c.tenant_id == tenant_id, dossiers.c.retire_le.is_not(None))
                .order_by(dossiers.c.id)
            ).all()
        return tuple(_vers_dossier(ligne) for ligne in lignes)

    def restaurer(self, dossier_id: DossierId) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                update(dossiers).where(dossiers.c.id == dossier_id).values(retire_le=None)
            )

    def par_contact_nr(self, contact_nr: str) -> Dossier | None:
        # Utilisé uniquement par `synchro_digifactory` (rôle `user`,
        # administratif, jamais un utilisateur final) : pas de dossier_id
        # connu à l'avance pour poser un contexte RLS pertinent, et ce
        # rôle n'est de toute façon pas soumis aux policies.
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(dossiers).where(dossiers.c.contact_nr == contact_nr)
            ).first()
        return _vers_dossier(ligne) if ligne is not None else None


def _vers_dossier(ligne: Any) -> Dossier:
    return Dossier(
        id=DossierId(ligne.id),
        tenant_id=TenantId(ligne.tenant_id),
        forme_juridique=ligne.forme_juridique,
        regime_imposition=ligne.regime_imposition,
        regime_tva=ligne.regime_tva,
        nom=ligne.nom,
        tva_recettes_regime=ligne.tva_recettes_regime,
        exercice_debut=ligne.exercice_debut,
        plateformes=tuple(ligne.plateformes),
        mode_acces_bancaire=ligne.mode_acces_bancaire,
        contact_nr=ligne.contact_nr,
        exercice_fin=ligne.exercice_fin,
        identite=identite_depuis_json(ligne.identite),
        retire_le=ligne.retire_le,
        pack_metier=ligne.pack_metier,
        option_ir_debut=ligne.option_ir_debut,
        relance_consentement=ligne.relance_consentement,
        code_naf=ligne.code_naf,
        a_confirmer=tuple(ligne.a_confirmer or ()),
    )


def _vers_tenant(ligne: Any) -> Tenant:
    return Tenant(
        id=TenantId(ligne.id), nom=ligne.nom, relance_consentement=ligne.relance_consentement
    )
