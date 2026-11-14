"""Carte des users Rollee déjà lus (empreintes, aperçu masqué).

Rien en clair : le passage suivant compare cette carte et ne rappelle
Rollee que pour les users qui n'y sont pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from axelcompta.core.ids import TenantId

from .rapprochement_rollee import Apercu, Empreintes, UserRollee


class CartesRollee(Protocol):
    def lire(self, tenant_id: TenantId, branchement_id: str) -> dict[str, UserRollee]:
        """Les users déjà lus de ce compte Rollee, par identifiant."""
        ...

    def garder(
        self, tenant_id: TenantId, branchement_id: str, user: UserRollee, le: datetime
    ) -> None:
        """Pose ou remplace la fiche de ce user."""
        ...

    def du_portefeuille(self, tenant_id: TenantId) -> list[tuple[str, UserRollee]]:
        """Chaque user lu du portefeuille, avec le compte Rollee d'où il vient."""
        ...


@dataclass
class CartesRolleeMemoire:
    fiches: dict[tuple[str, str, str], UserRollee] = field(default_factory=dict)

    def lire(self, tenant_id: TenantId, branchement_id: str) -> dict[str, UserRollee]:
        return {
            user_id: user
            for (tenant, branchement, user_id), user in self.fiches.items()
            if tenant == str(tenant_id) and branchement == branchement_id
        }

    def garder(
        self, tenant_id: TenantId, branchement_id: str, user: UserRollee, le: datetime
    ) -> None:
        del le
        self.fiches[(str(tenant_id), branchement_id, user.user_id)] = user

    def du_portefeuille(self, tenant_id: TenantId) -> list[tuple[str, UserRollee]]:
        return [
            (branchement, user)
            for (tenant, branchement, _user_id), user in self.fiches.items()
            if tenant == str(tenant_id)
        ]


def empreintes_json(empreintes: Empreintes) -> dict[str, list[str]]:
    return {
        "ibans": sorted(empreintes.ibans),
        "noms": sorted(empreintes.noms),
        "emails": sorted(empreintes.emails),
        "telephones": sorted(empreintes.telephones),
    }


def apercu_json(
    apercu: Apercu, comptes: tuple[tuple[str, str, str], ...] = ()
) -> dict[str, object]:
    corps: dict[str, object] = {
        "initiales": apercu.initiales,
        "plateformes": list(apercu.plateformes),
        "iban_fin": apercu.iban_fin,
        "nom": apercu.nom,
        "email_masque": apercu.email_masque,
    }
    if comptes:
        corps["comptes"] = [
            {"account_id": account, "plateforme": plateforme, "empreinte": empreinte_nom}
            for account, plateforme, empreinte_nom in comptes
        ]
    return corps


def sans_nom(user: UserRollee) -> bool:
    """Compte flotte déjà vu, dont le profil n'a pas encore donné de nom."""
    return bool(user.apercu.plateformes) and not user.empreintes.noms


def user_depuis(
    user_id: str,
    dossier_metadata: str | None,
    empreintes: dict[str, list[str]],
    apercu: dict[str, object],
    accounts_number: int | None = None,
    nom: str | None = None,
    email_masque: str | None = None,
) -> UserRollee:
    nom_clair = nom if nom is not None else str(apercu.get("nom") or "")
    masque = email_masque if email_masque is not None else apercu.get("email_masque")
    fin = apercu.get("iban_fin")
    comptes = _comptes(apercu)
    return UserRollee(
        user_id,
        dossier_metadata,
        Empreintes(
            frozenset(empreintes.get("ibans") or ()),
            frozenset(empreintes.get("noms") or ()),
            frozenset(empreintes.get("emails") or ()),
            frozenset(empreintes.get("telephones") or ()),
        ),
        Apercu(
            str(apercu.get("initiales") or ""),
            tuple(apercu.get("plateformes") or ()),  # type: ignore[arg-type]
            fin if isinstance(fin, str) else None,
            nom_clair,
            masque if isinstance(masque, str) else None,
        ),
        accounts_number,
        tuple((account, empreinte_nom) for account, _plateforme, empreinte_nom in comptes),
        comptes,
    )


def _comptes(apercu: dict[str, object]) -> tuple[tuple[str, str, str], ...]:
    brut = apercu.get("comptes")
    if not isinstance(brut, list):
        return ()
    lignes = []
    for ligne in brut:
        if not isinstance(ligne, dict) or not ligne.get("account_id"):
            continue
        lignes.append(
            (
                str(ligne.get("account_id")),
                str(ligne.get("plateforme") or ""),
                str(ligne.get("empreinte") or ""),
            )
        )
    return tuple(lignes)
