"""Orchestration multi-dossiers des notifications internes."""

from __future__ import annotations

from datetime import date, datetime

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaireMemoire,
    CompteReleve,
    relever_comptes,
)
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.notifier import notifier_portefeuille
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.decisions import DecisionHumaine, DecisionRepository
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository
from axelcompta.workflow.notifications import (
    TYPE_A_TRANCHER,
    TYPE_COMPTES_A_CHOISIR,
    InMemoryNotificationRepository,
)

T0 = datetime(2026, 9, 22, 9, 0)


def _dossier(id_: str) -> Dossier:
    return Dossier(
        id=DossierId(id_),
        tenant_id=TenantId("t"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="franchise",
        nom=id_,
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 1),
    )


def _ledger_avec_attente(*ids: str) -> InMemoryLedgerService:
    ledger = InMemoryLedgerService()
    m = Money(500)
    for id_ in ids:
        ledger.enregistrer(
            Ecriture(
                id=EcritureId(f"{id_}:1"),
                dossier_id=DossierId(id_),
                journal=Journal.BQ,
                date=date(2026, 3, 1),
                libelle="x",
                reference_piece=None,
                lignes=(
                    LigneEcriture(compte="512", sens=Sens.CREDIT, montant=m),
                    LigneEcriture(compte="471", sens=Sens.DEBIT, montant=m),
                ),
            )
        )
    return ledger


class _DecisionsQuiEchouentSurB(InMemoryDecisionRepository):
    def lister_decisions(self, dossier_id: DossierId) -> tuple[DecisionHumaine, ...]:
        if dossier_id == "b":
            raise ConnectionError("base")
        return super().lister_decisions(dossier_id)


def test_chaque_dossier_en_attente_est_notifie_et_un_echec_ne_bloque_pas_les_autres() -> None:
    notifications = InMemoryNotificationRepository()
    decisions: DecisionRepository = _DecisionsQuiEchouentSurB()

    resultats = notifier_portefeuille(
        tuple(_dossier(i) for i in "abcd"),
        _ledger_avec_attente("a", "b", "c"),
        decisions,
        notifications,
        T0,
    )

    statuts = {r.dossier_id: r.statut for r in resultats if r.type == TYPE_A_TRANCHER}
    assert statuts == {"a": "creee", "b": "echec", "c": "creee", "d": "rien_a_faire"}
    assert sorted(n.dossier_id for n in notifications.historique) == ["a", "c"]


def test_un_dossier_dont_un_compte_attend_un_choix_est_notifie() -> None:
    """AXE-851 : le premier relevé montre deux comptes, aucun n'est retenu
    d'office ; le dirigeant est prévenu dans sa cloche."""
    comptes = CompteBancaireMemoire()
    releves = [CompteReleve("pro", None, None), CompteReleve("perso", None, None)]
    relever_comptes(comptes, DossierId("a"), releves, T0)
    notifications = InMemoryNotificationRepository()

    resultats = notifier_portefeuille(
        (_dossier("a"), _dossier("b")),
        InMemoryLedgerService(),
        InMemoryDecisionRepository(),
        notifications,
        T0,
        comptes_bancaires=comptes,
    )

    statuts = {r.dossier_id: r.statut for r in resultats if r.type == TYPE_COMPTES_A_CHOISIR}
    assert statuts == {"a": "creee", "b": "rien_a_faire"}
