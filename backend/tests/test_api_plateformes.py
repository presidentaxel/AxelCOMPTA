"""AXE-819 : routes Rollee Connect, côté chauffeur et côté gestionnaire."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import axelcompta.api.routes as routes
from axelcompta.api.routes import get_services_rollee
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.plateformes_rollee import Session
from axelcompta.tenants.branchements import BranchementsMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
from tests.test_plateformes_rollee import _services


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _client() -> TestClient:
    client = _client_et_stubs()[0]
    services, _journal, _ = _services()
    services.branchements = BranchementsMemoire()  # aucun branchement : erreur lisible
    services.comptes = ComptesRolleeMemoire()
    client.app.dependency_overrides[get_services_rollee] = lambda: services  # type: ignore[attr-defined]
    return client


def test_le_chauffeur_ouvre_un_lien_rollee_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    async def lien(_s: object, dossier: object) -> Session:
        return Session("https://connect/x", None)

    monkeypatch.setattr(routes, "ouvrir_session", lien)
    reponse = _client().post(
        "/dossiers/DEMO_karim/plateformes/session", headers=_en_tete("DEMO_karim")
    )
    assert reponse.status_code == 200 and reponse.json()["lien"] == "https://connect/x"


def test_sans_rollee_branche_l_ecran_le_dit_et_le_lien_est_refuse() -> None:
    client = _client()
    lu = client.get("/dossiers/DEMO_karim/plateformes", headers=_en_tete("DEMO_karim"))
    assert lu.status_code == 200 and lu.json()["comptes"] == []
    assert "gestionnaire" in (lu.json()["erreur"] or "")
    refuse = client.post("/dossiers/DEMO_karim/plateformes/session", headers=_en_tete("DEMO_karim"))
    assert refuse.status_code == 409


def test_un_autre_chauffeur_n_ouvre_pas_le_lien_d_un_dossier() -> None:
    reponse = _client().post(
        "/dossiers/DEMO_karim/plateformes/session", headers=_en_tete("DEMO_sophie")
    )
    assert reponse.status_code == 403


def test_le_gestionnaire_ne_voit_qu_une_synthese_sans_montant() -> None:
    reponse = _client().get(
        "/dossiers/DEMO_karim/plateformes/synthese", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 200
    assert set(reponse.json()) == {"reliees", "attendues", "a_reconnecter", "manquantes"}
