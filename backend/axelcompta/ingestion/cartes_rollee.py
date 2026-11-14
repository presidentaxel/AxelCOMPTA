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


def empreintes_json(empreintes: Empreintes) -> dict[str, list[str]]:
    return {
        "ibans": sorted(empreintes.ibans),
        "noms": sorted(empreintes.noms),
        "emails": sorted(empreintes.emails),
        "telephones": sorted(empreintes.telephones),
    }


def apercu_json(apercu: Apercu) -> dict[str, object]:
    return {
        "initiales": apercu.initiales,
        "plateformes": list(apercu.plateformes),
        "iban_fin": apercu.iban_fin,
    }


def user_depuis(
    user_id: str,
    dossier_metadata: str | None,
    empreintes: dict[str, list[str]],
    apercu: dict[str, object],
) -> UserRollee:
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
            apercu.get("iban_fin") if isinstance(apercu.get("iban_fin"), str) else None,
        ),
    )
