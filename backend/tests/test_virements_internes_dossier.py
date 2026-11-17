"""AXE-968 : le passage horaire reprend les virements internes d'un dossier
dans tout le grand livre, sans toucher ce qu'un humain a classé."""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.tenants.models import Dossier
from axelcompta.virements_internes_dossier import reprendre
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository

D = DossierId("d")
DOSSIER = Dossier(
    id=D,
    tenant_id=TenantId("t"),
    forme_juridique="SARL",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="MK",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
)


def _operation(id_: str, montant: int, jour: int, compte: str = "471") -> Ecriture:
    banque, autre = (Sens.DEBIT, Sens.CREDIT) if montant > 0 else (Sens.CREDIT, Sens.DEBIT)
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 11, jour),
        libelle="trésorerie",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", banque, Money(abs(montant))),
            LigneEcriture(compte, autre, Money(abs(montant))),
        ),
    )


def _solde(ledger: InMemoryLedgerService, compte: str) -> int:
    return sum(
        (1 if x.sens is Sens.DEBIT else -1) * x.montant.centimes
        for e in ledger.grand_livre(D)
        for x in e.lignes
        if x.compte == compte
    )


def test_la_seconde_jambe_arrivee_plus_tard_retrouve_la_premiere() -> None:
    ledger = InMemoryLedgerService()
    ledger.enregistrer(_operation("s", -50_00, 12))
    decisions = InMemoryDecisionRepository()
    assert reprendre([DOSSIER], ledger, decisions, {}) == ""  # une jambe seule : rien

    ledger.enregistrer(_operation("e", 50_00, 12))  # synchro suivante
    assert reprendre([DOSSIER], ledger, decisions, {}) == ("virements internes : 1 paire(s) au 580")
    assert _solde(ledger, "471") == 0
    assert reprendre([DOSSIER], ledger, decisions, {}) == ""  # rejouer : rien de plus


def test_une_operation_deja_classee_reste_ou_elle_est() -> None:
    ledger = InMemoryLedgerService()
    ledger.enregistrer(_operation("s", -50_00, 12, compte="645"))
    ledger.enregistrer(_operation("e", 50_00, 12))
    assert reprendre([DOSSIER], ledger, InMemoryDecisionRepository(), {}) == ""
    assert _solde(ledger, "645") == 50_00
