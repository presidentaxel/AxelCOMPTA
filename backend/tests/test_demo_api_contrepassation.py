"""Une contre-passation reprend la décision humaine de son originale : la
paire s'annule dans le ledger servi à la liasse et aux exports."""

from __future__ import annotations

from datetime import date, datetime

from axelcompta.api.routes import _ledger_avec_decisions
from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository

DOSSIER = Dossier(
    id=DossierId("d1"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="Test",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
)


def test_la_contre_passation_suit_la_decision_de_loriginale() -> None:
    m = Money(2500)
    originale = Ecriture(
        id=EcritureId("d1:digifactory-t1"),
        dossier_id=DOSSIER.id,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="ZARA",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte="471", sens=Sens.DEBIT, montant=m),
            LigneEcriture(compte="512", sens=Sens.CREDIT, montant=m),
        ),
    )
    base = InMemoryLedgerService()
    base.enregistrer(originale)
    base.enregistrer(contrepasser(originale))
    decisions = InMemoryDecisionRepository()
    decisions.enregistrer_decision(
        DecisionHumaine(
            DOSSIER.id,
            originale.id,
            "usage_personnel",
            Etage.REGLE,
            0.5,
            UserId("u"),
            datetime(2026, 3, 2),
        )
    )

    ledger = _ledger_avec_decisions(DOSSIER, base, decisions)

    soldes: dict[str, int] = {}
    for ecriture in ledger.grand_livre(DOSSIER.id):
        for ligne in ecriture.lignes:
            signe = 1 if ligne.sens is Sens.DEBIT else -1
            soldes[ligne.compte] = soldes.get(ligne.compte, 0) + signe * ligne.montant.centimes
    assert "471" not in soldes
    assert soldes == {"455": 0, "512": 0}
