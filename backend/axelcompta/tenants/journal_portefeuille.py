"""Journal du portefeuille (AXE-812) : ce qui arrive au portefeuille, pas à
un dossier. Connexions des membres, réinitialisation de la double
authentification d'un membre par un autre admin. Ajout seul : une ligne ne
se modifie ni ne s'efface (trigger en base)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from axelcompta.core.ids import TenantId, UserId

ACTE_CONNEXION_MEMBRE = "connexion"
ACTE_MFA_REINITIALISEE = "mfa_reinitialisee"


class JournalPortefeuille(Protocol):
    def noter(
        self, tenant_id: TenantId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ActePortefeuille:
    tenant_id: TenantId
    type_acte: str
    reference: str
    acteur: UserId
    le: datetime


@dataclass
class JournalPortefeuilleMemoire:
    actes: list[ActePortefeuille] = field(default_factory=list)

    def noter(
        self, tenant_id: TenantId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None:
        self.actes.append(ActePortefeuille(tenant_id, type_acte, reference, acteur, le))
