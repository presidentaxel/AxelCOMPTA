"""`LiensRollee` sur Postgres (AXE-911, migration `e2a6c8f4b913`)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine, Row
from sqlalchemy.exc import IntegrityError

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls
from axelcompta.tenants.orm import dossiers

from .liens_rollee import AChoisir, Lien, LienDejaPris, LienRetire
from .orm import liens_rollee_retires, rapprochements_rollee, utilisateurs_rollee
from .rapprochement_rollee import Apercu, Candidat


def _utc(valeur: datetime) -> datetime:
    return valeur if valeur.tzinfo is not None else valeur.replace(tzinfo=UTC)


def _lien(ligne: Row[Any]) -> Lien:
    return Lien(
        dossier_id=DossierId(ligne.dossier_id),
        rollee_user_id=ligne.rollee_user_id,
        branchement_id=ligne.branchement_id,
        origine=ligne.origine,
        relie_le=_utc(ligne.cree_le if hasattr(ligne, "cree_le") else ligne.relie_le),
        indice=ligne.indice,
        relie_par=ligne.relie_par,
    )


def _attente(ligne: Row[Any]) -> AChoisir:
    return AChoisir(
        rollee_user_id=ligne.rollee_user_id,
        tenant_id=TenantId(ligne.tenant_id),
        branchement_id=ligne.branchement_id,
        etat=ligne.etat,
        candidats=tuple(
            Candidat(c["dossier_id"], tuple(c["raisons"]), bool(c["sur"])) for c in ligne.candidats
        ),
        apercu=Apercu(
            ligne.apercu.get("initiales", ""),
            tuple(ligne.apercu.get("plateformes", ())),
            ligne.apercu.get("iban_fin"),
        ),
        maj_le=_utc(ligne.maj_le),
    )


def _valeurs_attente(a: AChoisir) -> dict[str, Any]:
    return {
        "rollee_user_id": a.rollee_user_id,
        "tenant_id": str(a.tenant_id),
        "branchement_id": a.branchement_id,
        "etat": a.etat,
        "candidats": [
            {"dossier_id": c.dossier_id, "raisons": list(c.raisons), "sur": c.sur}
            for c in a.candidats
        ],
        "apercu": {
            "initiales": a.apercu.initiales,
            "plateformes": list(a.apercu.plateformes),
            "iban_fin": a.apercu.iban_fin,
        },
        "maj_le": a.maj_le,
    }


class PostgresLiensRollee:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def liens(self, tenant_id: TenantId) -> list[Lien]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(utilisateurs_rollee)
                .join(dossiers, dossiers.c.id == utilisateurs_rollee.c.dossier_id)
                .where(dossiers.c.tenant_id == str(tenant_id))
                .order_by(utilisateurs_rollee.c.dossier_id, utilisateurs_rollee.c.rollee_user_id)
            ).all()
        return [_lien(ligne) for ligne in lignes]

    def liens_du(self, dossier_id: DossierId) -> list[Lien]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(utilisateurs_rollee)
                .where(utilisateurs_rollee.c.dossier_id == dossier_id)
                .order_by(utilisateurs_rollee.c.cree_le, utilisateurs_rollee.c.rollee_user_id)
            ).all()
        return [_lien(ligne) for ligne in lignes]

    def lien(self, dossier_id: DossierId) -> Lien | None:
        trouves = self.liens_du(dossier_id)
        return trouves[0] if trouves else None

    def historique(self, dossier_id: DossierId) -> list[LienRetire]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(liens_rollee_retires)
                .where(liens_rollee_retires.c.dossier_id == dossier_id)
                .order_by(liens_rollee_retires.c.retire_le.desc())
            ).all()
        return [LienRetire(_lien(r), _utc(r.retire_le), r.retire_par, r.motif) for r in lignes]

    def lier(self, lien: Lien) -> None:
        try:
            with self._engine.begin() as connexion:
                appliquer_rls(connexion)
                connexion.execute(
                    insert(utilisateurs_rollee).values(
                        dossier_id=lien.dossier_id,
                        rollee_user_id=lien.rollee_user_id,
                        branchement_id=lien.branchement_id,
                        cree_le=lien.relie_le,
                        origine=lien.origine,
                        indice=lien.indice,
                        relie_par=lien.relie_par,
                    )
                )
        except IntegrityError as exc:
            raise LienDejaPris("Ce compte Rollee est déjà relié.") from exc

    def delier(
        self,
        dossier_id: DossierId,
        par: str,
        motif: str,
        le: datetime,
        rollee_user_id: str | None = None,
    ) -> Lien | None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            if rollee_user_id is None:
                poses = connexion.execute(
                    select(utilisateurs_rollee.c.rollee_user_id).where(
                        utilisateurs_rollee.c.dossier_id == dossier_id
                    )
                ).scalars()
                ids = list(poses)
                if len(ids) > 1:
                    raise LienDejaPris("Plusieurs comptes Rollee : précisez lequel retirer.")
                rollee_user_id = ids[0] if ids else None
            if rollee_user_id is None:
                return None
            ligne = connexion.execute(
                delete(utilisateurs_rollee)
                .where(
                    utilisateurs_rollee.c.dossier_id == dossier_id,
                    utilisateurs_rollee.c.rollee_user_id == rollee_user_id,
                )
                .returning(*utilisateurs_rollee.c)
            ).first()
            if ligne is None:
                return None
            lien = _lien(ligne)
            _garder(connexion, lien, par, motif, le)
        return lien

    def paires_retirees(self, tenant_id: TenantId) -> frozenset[tuple[str, str]]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(liens_rollee_retires.c.rollee_user_id, liens_rollee_retires.c.dossier_id)
                .join(dossiers, dossiers.c.id == liens_rollee_retires.c.dossier_id)
                .where(dossiers.c.tenant_id == str(tenant_id))
            ).all()
        return frozenset((ligne.rollee_user_id, ligne.dossier_id) for ligne in lignes)

    def ecarter(self, rollee_user_id: str, le: datetime) -> bool:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            resultat = connexion.execute(
                update(rapprochements_rollee)
                .where(rapprochements_rollee.c.rollee_user_id == rollee_user_id)
                .values(etat="ecarte", candidats=[], maj_le=le)
            )
        return resultat.rowcount == 1

    def a_choisir(self, tenant_id: TenantId) -> list[AChoisir]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(rapprochements_rollee)
                .where(rapprochements_rollee.c.tenant_id == str(tenant_id))
                .order_by(rapprochements_rollee.c.rollee_user_id)
            ).all()
        return [_attente(ligne) for ligne in lignes]

    def remplacer_a_choisir(
        self, tenant_id: TenantId, branchement_id: str, attente: Sequence[AChoisir]
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(rapprochements_rollee).where(
                    rapprochements_rollee.c.tenant_id == str(tenant_id),
                    rapprochements_rollee.c.branchement_id == branchement_id,
                )
            )
            if attente:
                connexion.execute(
                    insert(rapprochements_rollee), [_valeurs_attente(a) for a in attente]
                )

    def retirer_a_choisir(self, rollee_user_id: str) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                delete(rapprochements_rollee).where(
                    rapprochements_rollee.c.rollee_user_id == rollee_user_id
                )
            )


def _garder(connexion: Connection, lien: Lien, par: str, motif: str, le: datetime) -> None:
    connexion.execute(
        insert(liens_rollee_retires).values(
            id=uuid.uuid4().hex,
            dossier_id=lien.dossier_id,
            rollee_user_id=lien.rollee_user_id,
            branchement_id=lien.branchement_id,
            origine=lien.origine,
            indice=lien.indice,
            relie_par=lien.relie_par,
            relie_le=lien.relie_le,
            retire_le=le,
            retire_par=par,
            motif=motif,
        )
    )
