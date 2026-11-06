"""Contacts Digifactory proposés au gestionnaire, et ses décisions (AXE-845).

La détection réécrit la proposition d'un contact (dernière lecture Sirene).
Les décisions sont append-only : la dernière fait foi. « ajouter » attend
que le worker crée le dossier ; « ignorer » retire la proposition de la
liste ; « reprendre » la remet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

from axelcompta.core.ids import TenantId

DecisionContact = Literal["ajouter", "ignorer", "reprendre"]
DECISIONS: frozenset[str] = frozenset({"ajouter", "ignorer", "reprendre"})


@dataclass(frozen=True, slots=True)
class PropositionStockee:
    contact_nr: str
    nom: str
    siren: str | None
    forme: str | None
    exercice_debut: date | None
    code_naf: str | None
    avertissements: tuple[str, ...]
    cessee: bool
    detecte_le: datetime


class ContactsProposesRepository(Protocol):
    def remplacer_propositions(
        self, tenant_id: TenantId, propositions: list[PropositionStockee]
    ) -> None:
        """Les propositions du portefeuille deviennent exactement celles-ci
        (un contact qui a eu son dossier en sort)."""
        ...

    def propositions(self, tenant_id: TenantId) -> list[PropositionStockee]: ...

    def decider(
        self,
        tenant_id: TenantId,
        contact_nr: str,
        decision: DecisionContact,
        par: str,
        le: datetime,
    ) -> None: ...

    def decisions(self, tenant_id: TenantId) -> dict[str, DecisionContact]:
        """La dernière décision par contact."""
        ...


class ContactsProposesMemoire:
    def __init__(self) -> None:
        self._propositions: dict[TenantId, list[PropositionStockee]] = {}
        self._decisions: list[tuple[TenantId, str, DecisionContact]] = []

    def remplacer_propositions(
        self, tenant_id: TenantId, propositions: list[PropositionStockee]
    ) -> None:
        self._propositions[tenant_id] = list(propositions)

    def propositions(self, tenant_id: TenantId) -> list[PropositionStockee]:
        return list(self._propositions.get(tenant_id, []))

    def decider(
        self,
        tenant_id: TenantId,
        contact_nr: str,
        decision: DecisionContact,
        par: str,
        le: datetime,
    ) -> None:
        self._decisions.append((tenant_id, contact_nr, decision))

    def decisions(self, tenant_id: TenantId) -> dict[str, DecisionContact]:
        return {nr: d for t, nr, d in self._decisions if t == tenant_id}
