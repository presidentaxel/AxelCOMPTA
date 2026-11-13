"""AXE-855 : le moyen de paiement s'affiche aussi dans les sujets du mode expert."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_propositions
from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_expert,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

KARIM = DossierId("DEMO_karim")
PLEIN = EcritureId("DEMO_karim:digifactory-plein")
VIREMENT = EcritureId("DEMO_karim:digifactory-virement")


def _a_trancher(client: TestClient, ecriture_id: EcritureId, moyen: str | None) -> None:
    _ledger_du_client(client).enregistrer(
        Ecriture(
            id=ecriture_id,
            dossier_id=KARIM,
            journal=Journal.BQ,
            date=date(2026, 3, 1),
            libelle="PAIEMENT CARBURANT",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(60_00)),
                LigneEcriture("471", Sens.DEBIT, Money(60_00)),
            ),
        )
    )
    propositions = client.app.dependency_overrides[get_propositions]()  # type: ignore[attr-defined]
    propositions.enregistrer(
        ecriture_id,
        ProposedEntry(
            KARIM,
            TransactionId(ecriture_id),
            "carburant",
            Etage.ML,
            0.4,
            moyen_paiement=moyen,
        ),
    )


def test_un_sujet_d_operation_bancaire_dit_comment_l_argent_est_sorti() -> None:
    client = _client_expert()
    _a_trancher(client, PLEIN, "card")
    _a_trancher(client, VIREMENT, None)

    sujets = client.get("/expert/file", headers=_en_tete_gestionnaire()).json()["sujets"]

    par_ecriture = {s["ecriture_id"]: s for s in sujets if s["nature"] == "a_trancher"}
    assert par_ecriture[PLEIN]["moyen_paiement"] == "card"
    assert par_ecriture[VIREMENT]["moyen_paiement"] is None
