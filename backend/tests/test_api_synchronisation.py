"""AXE-845 : bouton « Synchroniser » et nouveaux chauffeurs Digifactory."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.core.ids import TenantId
from axelcompta.demo_api import get_contacts_proposes, get_demandes_jobs
from axelcompta.jobs.file import FileMemoire
from axelcompta.tenants.contacts_proposes import ContactsProposesMemoire, PropositionStockee
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()
T = TenantId("TENANT_DEMO")


def _client(role: str = "admin") -> tuple[TestClient, FileMemoire, ContactsProposesMemoire]:
    client = _client_et_stubs(role)[0]
    app = cast(FastAPI, client.app)
    file, contacts = FileMemoire(), ContactsProposesMemoire()
    contacts.remplacer_propositions(
        T,
        [
            PropositionStockee(
                "10",
                "VTC NORD",
                "111111111",
                "SAS",
                date(2026, 3, 13),
                "49.32Z",
                (),
                False,
                datetime.now(UTC),
            )
        ],
    )
    app.dependency_overrides[get_demandes_jobs] = lambda: file
    app.dependency_overrides[get_contacts_proposes] = lambda: contacts
    return client, file, contacts


def test_deux_clics_ne_lancent_qu_une_synchro() -> None:
    client, file, _ = _client()
    assert client.get("/portefeuille/synchronisation", headers=EN_TETE).json() is None

    premier = client.post("/portefeuille/synchroniser", headers=EN_TETE).json()
    second = client.post("/portefeuille/synchroniser", headers=EN_TETE).json()

    assert premier["statut"] == second["statut"] == "en_attente"
    job = file.prendre("worker")
    assert job is not None and file.prendre("worker") is None  # une seule demande
    file.terminer(job.id)
    suivi = client.get("/portefeuille/synchronisation", headers=EN_TETE).json()
    assert suivi["statut"] == "fait"


def test_ajouter_un_chauffeur_demande_la_synchro_qui_le_cree() -> None:
    client, file, contacts = _client()
    (propose,) = client.get("/portefeuille/nouveaux-chauffeurs", headers=EN_TETE).json()
    assert (propose["contact_nr"], propose["decision"]) == ("10", None)

    reponse = client.post(
        "/portefeuille/nouveaux-chauffeurs",
        json={"contact_nrs": ["10"], "decision": "ajouter"},
        headers=EN_TETE,
    )

    assert reponse.json()[0]["decision"] == "ajouter"
    assert contacts.decisions(T) == {"10": "ajouter"}
    assert file.dernier(T, "synchro_digifactory") is not None


def test_ignorer_puis_reprendre_et_droits() -> None:
    client, _, _ = _client()
    for decision, attendu in (("ignorer", "ignorer"), ("reprendre", None)):
        reponse = client.post(
            "/portefeuille/nouveaux-chauffeurs",
            json={"contact_nrs": ["10"], "decision": decision},
            headers=EN_TETE,
        )
        assert reponse.json()[0]["decision"] == attendu
    inconnu = client.post(
        "/portefeuille/nouveaux-chauffeurs",
        json={"contact_nrs": ["99"], "decision": "ajouter"},
        headers=EN_TETE,
    )
    assert inconnu.status_code == 404
    lecture = _client("lecture")[0]
    assert lecture.post("/portefeuille/synchroniser", headers=EN_TETE).status_code == 403
