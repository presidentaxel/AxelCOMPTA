"""AXE-845 : propositions et décisions en mémoire (même contrat que Postgres)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.ids import TenantId
from axelcompta.tenants.contacts_proposes import ContactsProposesMemoire, PropositionStockee

T = TenantId("t")
LE = datetime(2026, 11, 6, tzinfo=UTC)


def _proposition(numero: str) -> PropositionStockee:
    return PropositionStockee(
        numero, f"C{numero}", None, "SAS", date(2026, 1, 1), None, (), False, LE
    )


def test_les_propositions_sont_remplacees_et_la_derniere_decision_fait_foi() -> None:
    depot = ContactsProposesMemoire()
    depot.remplacer_propositions(T, [_proposition("1"), _proposition("2")])
    depot.remplacer_propositions(T, [_proposition("2")])
    assert [p.contact_nr for p in depot.propositions(T)] == ["2"]
    depot.decider(T, "2", "ignorer", "louis", LE)
    depot.decider(T, "2", "reprendre", "louis", LE)
    assert depot.decisions(T) == {"2": "reprendre"}
    assert depot.propositions(TenantId("autre")) == [] and depot.decisions(TenantId("autre")) == {}
