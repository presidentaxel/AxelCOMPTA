"""AXE-852 contre un vrai Postgres : une décision et son OD de reclassement
s'écrivent dans la même transaction. Si l'OD est refusée, la décision n'est
pas gardée."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.engine import Engine

from axelcompta.categorize.models import Etage
from axelcompta.core.errors import InvariantViole
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_et_reclassements import PostgresDecisionsEtReclassements
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository

pytestmark = pytest.mark.integration


def _ecriture(dossier: DossierId, identifiant: str, debit: int, credit: int) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=dossier,
        journal=Journal.OD,
        date=date(2026, 6, 1),
        libelle="Reclassement",
        reference_piece=None,
        lignes=(
            LigneEcriture("6061", Sens.DEBIT, Money(debit)),
            LigneEcriture("471", Sens.CREDIT, Money(credit)),
        ),
    )


def _decision(dossier: DossierId, source: str) -> DecisionHumaine:
    return DecisionHumaine(
        dossier_id=dossier,
        ecriture_id=EcritureId(source),
        categorie="carburant",
        etage_origine=Etage.ML,
        confiance_origine=0.4,
        decide_par=UserId("dirigeant"),
        decide_le=datetime(2026, 11, 9, 10, tzinfo=UTC),
    )


@pytest.fixture
def dossier(engine: Engine, creer_dossier: Callable[[str], None], id_unique: str) -> DossierId:
    creer_dossier(id_unique)
    dossier_id = DossierId(id_unique)
    source = Ecriture(
        id=EcritureId(f"{id_unique}:s"),
        dossier_id=dossier_id,
        journal=Journal.BQ,
        date=date(2026, 6, 1),
        libelle="CARTE TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("471", Sens.DEBIT, Money(60_00)),
            LigneEcriture("512", Sens.CREDIT, Money(60_00)),
        ),
    )
    PostgresLedgerService(engine).enregistrer(source)
    return dossier_id


def test_la_decision_et_son_od_sont_ecrites_ensemble(engine: Engine, dossier: DossierId) -> None:
    source = f"{dossier}:s"
    od = _ecriture(dossier, f"{source}:decision-1", 60_00, 60_00)

    PostgresDecisionsEtReclassements(engine).ecrire([_decision(dossier, source)], [od])

    assert len(PostgresDecisionRepository(engine).lister_decisions(dossier)) == 1
    ids = {e.id for e in PostgresLedgerService(engine).grand_livre(dossier)}
    assert od.id in ids


def test_une_od_refusee_ne_laisse_pas_la_decision(engine: Engine, dossier: DossierId) -> None:
    """Critère du ticket : l'écriture de l'OD échoue, aucune décision ne reste."""
    source = f"{dossier}:s"
    desequilibree = _ecriture(dossier, f"{source}:decision-1", 60_00, 59_99)

    with pytest.raises(InvariantViole, match="déséquilibrée"):
        PostgresDecisionsEtReclassements(engine).ecrire(
            [_decision(dossier, source)], [desequilibree]
        )

    assert PostgresDecisionRepository(engine).lister_decisions(dossier) == ()
    ids = {e.id for e in PostgresLedgerService(engine).grand_livre(dossier)}
    assert ids == {EcritureId(source)}
