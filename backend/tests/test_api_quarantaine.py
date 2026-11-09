"""AXE-424 : le gestionnaire voit la quarantaine et la résout."""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.demo_api import get_journal_ingestion
from axelcompta.ingestion.journal import InMemoryJournalIngestion
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

SOPHIE = DossierId("DEMO_sophie")
EN_TETE = _en_tete_gestionnaire()
ORIGINE = EcritureId("DEMO_sophie:digifactory-t1")


def _client_avec_une_modification(role: str = "admin") -> TestClient:
    client = _client_et_stubs(role)[0]
    ledger = _ledger_du_client(client)
    origine = Ecriture(
        id=ORIGINE,
        dossier_id=SOPHIE,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(60_00)),
            LigneEcriture("471", Sens.DEBIT, Money(60_00)),
        ),
    )
    ledger.enregistrer(origine)
    ledger.enregistrer(contrepasser(origine))
    app = cast(FastAPI, client.app)
    journal = cast(InMemoryJournalIngestion, app.dependency_overrides[get_journal_ingestion]())
    journal.mettre_en_quarantaine(
        SOPHIE,
        "digifactory",
        "modifiee_apres_comptabilisation",
        "t1",
        {
            "id": "t1",
            "provider_description": "CB TOTAL",
            "amount": -75.0,
            "date": "2026-03-01",
            "updated_at": "2026-03-05 10:00:00",
        },
    )
    return client


def test_le_gestionnaire_voit_l_operation_et_l_accepte() -> None:
    client = _client_avec_une_modification()
    (entree,) = client.get(f"/dossiers/{SOPHIE}/quarantaine", headers=EN_TETE).json()
    assert entree["motif"] == "modifiee_apres_comptabilisation"
    assert (entree["montant_cts"], entree["resoluble"], entree["decision"]) == (-75_00, True, None)

    reponse = client.post(
        f"/dossiers/{SOPHIE}/quarantaine/{entree['id']}",
        json={"decision": "accepter"},
        headers=EN_TETE,
    )

    assert reponse.status_code == 200
    assert reponse.json()["decision"] == "accepter"
    ids = {e.id for e in _ledger_du_client(client).grand_livre(SOPHIE)}
    assert f"{ORIGINE}:corrige-1" in ids
    deuxieme = client.post(
        f"/dossiers/{SOPHIE}/quarantaine/{entree['id']}",
        json={"decision": "ignorer"},
        headers=EN_TETE,
    )
    assert deuxieme.status_code == 409


def test_la_lecture_ne_resout_pas_et_une_entree_inconnue_est_404() -> None:
    lecture = _client_avec_une_modification("lecture")
    (entree,) = lecture.get(f"/dossiers/{SOPHIE}/quarantaine", headers=EN_TETE).json()
    refus = lecture.post(
        f"/dossiers/{SOPHIE}/quarantaine/{entree['id']}",
        json={"decision": "accepter"},
        headers=EN_TETE,
    )
    assert refus.status_code == 403
    admin = _client_avec_une_modification()
    inconnue = admin.post(
        f"/dossiers/{SOPHIE}/quarantaine/inconnue", json={"decision": "ignorer"}, headers=EN_TETE
    )
    assert inconnue.status_code == 404
