"""AXE-900 : les opérations suivies sont relues de la base."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.engine import Engine

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId, TransactionId, UserId
from axelcompta.workflow.decisions import CATEGORIE_ANNULATION, DecisionHumaine
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.indicateurs_categorisation_postgres import operations_suivies
from axelcompta.workflow.orm import propositions_categorisation
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository

pytestmark = pytest.mark.integration

D = DossierId("d1")


def _decision(ecriture: str, categorie: str, le: datetime) -> DecisionHumaine:
    return DecisionHumaine(D, EcritureId(ecriture), categorie, Etage.ML, 0.4, UserId("u"), le)


def test_les_operations_datees_sont_relues_avec_leur_premiere_decision(
    engine: Engine,
    creer_dossier: Callable[[str], None],
    creer_ecriture: Callable[[str, str], None],
) -> None:
    creer_dossier("d1")
    propositions = PostgresPropositionRepository(engine)
    for ecriture in ("e1", "ancienne"):
        creer_ecriture("d1", ecriture)
        propositions.enregistrer(
            EcritureId(ecriture), ProposedEntry(D, TransactionId(ecriture), "repas", Etage.ML, 0.4)
        )
    with engine.begin() as connexion:  # une proposition d'avant AXE-900, sans date
        connexion.execute(
            update(propositions_categorisation)
            .where(propositions_categorisation.c.ecriture_id == "ancienne")
            .values(cree_le=None)
        )
    decisions = PostgresDecisionRepository(engine)
    premiere = datetime(2026, 11, 12, 9, tzinfo=UTC)
    decisions.enregistrer_decision(_decision("e1", CATEGORIE_ANNULATION, premiere))
    decisions.enregistrer_decision(_decision("e1", "repas", premiere + timedelta(hours=1)))
    decisions.enregistrer_decision(_decision("e1", "carburant", premiere + timedelta(hours=2)))

    (operation,) = operations_suivies(engine, datetime.now(UTC) - timedelta(days=30))

    assert (operation.etage, operation.categorie) == ("ML", "repas")
    assert operation.date_operation == date(2026, 3, 1)
    assert operation.a_trancher is True  # écrite au 471
    assert operation.decide_le == premiere + timedelta(hours=1)  # l'annulation ne compte pas
    assert operation.cree_le.tzinfo is not None
