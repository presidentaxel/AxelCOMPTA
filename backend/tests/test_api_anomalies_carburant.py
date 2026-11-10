"""AXE-836 : un petit montant carburant ressort dans Anomalies, avec le moyen
de paiement lu à la synchro."""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import FastAPI

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.demo_api import get_propositions
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.propositions import InMemoryPropositionRepository
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_expert,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

KARIM = DossierId("DEMO_karim")


def test_un_cafe_chez_total_ressort_avec_son_moyen_de_paiement() -> None:
    client = _client_expert()
    cafe = Ecriture(
        id=EcritureId("DEMO_karim:digifactory-cafe"),
        dossier_id=KARIM,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL ACCESS A6",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(1_50)),
            LigneEcriture("6061", Sens.DEBIT, Money(1_50)),
        ),
    )
    _ledger_du_client(client).enregistrer(cafe)
    propositions = cast(
        InMemoryPropositionRepository,
        cast(FastAPI, client.app).dependency_overrides[get_propositions](),
    )
    propositions.enregistrer(
        cafe.id,
        ProposedEntry(
            KARIM, TransactionId("cafe"), "carburant", Etage.REGLE, 0.5, moyen_paiement="card"
        ),
    )

    alertes = client.get(f"/dossiers/{KARIM}/anomalies", headers=_en_tete_gestionnaire()).json()

    (alerte,) = [a for a in alertes if a["id"] == f"carburant_petit_montant:{cafe.id}"]
    assert alerte["moyen_paiement"] == "card"
    assert alerte["detail"] == "Montant trop faible pour un plein."
