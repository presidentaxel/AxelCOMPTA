"""AXE-800 contre un vrai Postgres : une décision d'expert s'écrit avec ses
écritures, tout ou rien ; la plus récente habilitation fait foi."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.engine import Engine

from axelcompta.core.errors import InvariantViole
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.workflow.expert_comptable import DecisionExpert, Habilitation
from axelcompta.workflow.expert_comptable_postgres import PostgresExpertRepository

pytestmark = pytest.mark.integration

LE = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)


def _ecriture(dossier: DossierId, identifiant: str, credit: int) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=dossier,
        journal=Journal.OD,
        date=date(2026, 6, 1),
        libelle="Imputation",
        reference_piece=None,
        lignes=(
            LigneEcriture("6061", Sens.DEBIT, Money(60_00)),
            LigneEcriture("471", Sens.CREDIT, Money(credit)),
        ),
    )


def _decision(dossier: DossierId) -> DecisionExpert:
    return DecisionExpert(
        id="d-1",
        tenant_id=TenantId("t-test"),
        dossier_id=dossier,
        ecriture_id=EcritureId(f"{dossier}:s"),
        nature="imputation",
        motif="Plein de la flotte",
        auteur=UserId("expert"),
        auteur_nom="Claire Expert",
        version_engagement="v",
        le=LE,
    )


def test_la_decision_et_ses_ecritures_sont_ecrites_ensemble(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    experts = PostgresExpertRepository(engine)

    experts.decider(_decision(dossier), [_ecriture(dossier, f"{id_unique}:n", 60_00)])

    (decision,) = experts.decisions(dossier)
    assert decision.ecritures == (EcritureId(f"{id_unique}:n"),)
    assert [e.id for e in PostgresLedgerService(engine).grand_livre(dossier)] == [f"{id_unique}:n"]


def test_une_ecriture_refusee_ne_laisse_pas_de_decision(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    dossier = DossierId(id_unique)
    experts = PostgresExpertRepository(engine)

    with pytest.raises(InvariantViole):
        experts.decider(
            _decision(dossier),
            [_ecriture(dossier, f"{id_unique}:a", 60_00), _ecriture(dossier, f"{id_unique}:b", 1)],
        )

    assert experts.decisions(dossier) == ()
    assert PostgresLedgerService(engine).grand_livre(dossier) == ()


def test_la_plus_recente_habilitation_fait_foi(
    engine: Engine, creer_dossier: Callable[[str], None], id_unique: str
) -> None:
    creer_dossier(id_unique)
    experts = PostgresExpertRepository(engine)
    for jours, dossiers in ((0, ("a",)), (1, ("a", "b"))):
        experts.habiliter(
            Habilitation(
                tenant_id=TenantId("t-test"),
                email="Expert@Cabinet.fr",
                nom="Claire Expert",
                cabinet="Cabinet",
                numero_ordre="13-1",
                lettre_mission="LM",
                date_lettre=date(2026, 1, 1),
                dossiers=tuple(DossierId(d) for d in dossiers),
                accordee_par=UserId("admin"),
                accordee_le=LE + timedelta(days=jours),
            )
        )

    habilitation = experts.habilitation(TenantId("t-test"), "expert@cabinet.fr")

    assert habilitation is not None
    assert habilitation.dossiers == (DossierId("a"), DossierId("b"))
