"""AXE-819 : routes Rollee Connect, côté chauffeur et côté gestionnaire."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import axelcompta.api.routes as routes
from axelcompta.api.routes import get_liens_rollee, get_services_rollee, get_settlements
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.liens_rollee import LiensRolleeMemoire
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire
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
    client.app.dependency_overrides[get_settlements] = lambda: SettlementsMemoire()  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_liens_rollee] = lambda: LiensRolleeMemoire()  # type: ignore[attr-defined]
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


def test_le_gestionnaire_rapproche_une_entreprise_sans_lien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def phrase(_services: object, _dossier: object) -> str:
        return "Un seul compte Rollee correspond : le lien est posé."

    monkeypatch.setattr(routes, "_phrase_synchro_rollee", phrase)
    reponse = _client().post(
        "/dossiers/DEMO_karim/rollee/synchroniser", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 200
    assert reponse.json() == {"phrase": "Un seul compte Rollee correspond : le lien est posé."}


def test_l_avancement_de_la_synchro_se_lit() -> None:
    from axelcompta.rapprochement_rollee_service import retenir_avancement

    retenir_avancement("DEMO_karim")("Flotte : 10/100 comptes Rollee lus, environ 2 min.")
    reponse = _client().get(
        "/dossiers/DEMO_karim/rollee/synchroniser", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 200
    assert reponse.json()["phrase"] == "Flotte : 10/100 comptes Rollee lus, environ 2 min."


def test_la_lecture_seule_ne_synchronise_pas_rollee() -> None:
    client = _client_et_stubs(role="lecture")[0]
    services, _journal, _ = _services()
    client.app.dependency_overrides[get_services_rollee] = lambda: services  # type: ignore[attr-defined]
    reponse = client.post(
        "/dossiers/DEMO_karim/rollee/synchroniser", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 403


def test_le_gestionnaire_ne_voit_qu_une_synthese_sans_montant() -> None:
    reponse = _client().get(
        "/dossiers/DEMO_karim/plateformes/synthese", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 200
    assert set(reponse.json()) == {
        "reliees",
        "attendues",
        "a_reconnecter",
        "manquantes",
        "versements_a_verifier",
        "noms",
        "comptes",
    }
    assert reponse.json()["noms"] == []
    assert reponse.json()["comptes"] == []


def test_la_synthese_nomme_la_plateforme_a_reconnecter() -> None:
    from datetime import UTC, datetime

    from axelcompta.core.ids import DossierId
    from axelcompta.ingestion.comptes_rollee import CompteRelie

    client = _client_et_stubs()[0]
    services, _journal, _ = _services()
    services.branchements = BranchementsMemoire()
    comptes = ComptesRolleeMemoire()
    le = datetime(2026, 11, 14, tzinfo=UTC)
    karim = DossierId("DEMO_karim")
    comptes.remplacer_comptes(
        karim,
        [
            CompteRelie("uber", karim, "uber.com-rev", True, False, le, le),
            CompteRelie("bolt", karim, "bolt.eu-rev", False, False, None, le),
        ],
    )
    services.comptes = comptes
    client.app.dependency_overrides[get_services_rollee] = lambda: services  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_settlements] = lambda: SettlementsMemoire()  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_liens_rollee] = lambda: LiensRolleeMemoire()  # type: ignore[attr-defined]
    corps = client.get(
        "/dossiers/DEMO_karim/plateformes/synthese", headers=_en_tete_gestionnaire()
    ).json()
    assert corps["a_reconnecter"] == 1
    assert corps["comptes"] == [
        {
            "nom": "uber.com-rev",
            "etat": "connecte",
            "relie_le": "2026-11-14T00:00:00+00:00",
            "compte_rollee": "",
            "rollee_user_id": "",
        },
        {
            "nom": "bolt.eu-rev",
            "etat": "a_reconnecter",
            "relie_le": None,
            "compte_rollee": "",
            "rollee_user_id": "",
        },
    ]
