"""AXE-803 : le chauffeur enregistre son contrat de LOA."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

SOPHIE = "DEMO_sophie"
CONTRAT = {
    "loueur": "DIAC",
    "vehicule": "Renault Austral",
    "debut": "2026-04-01",
    "duree_mois": 36,
    "loyer_mensuel_cts": 45000,
    "premier_loyer_cts": 300000,
    "prix_levee_cts": 900000,
}


def _poster(client: TestClient, corps: dict[str, Any]) -> Any:
    return client.post(f"/dossiers/{SOPHIE}/loa", json=corps, headers=_en_tete(SOPHIE))


def test_un_contrat_s_enregistre_et_se_relit() -> None:
    client = _client()
    reponse = _poster(client, CONTRAT)
    assert reponse.status_code == 200, reponse.text
    (vue,) = client.get(f"/dossiers/{SOPHIE}/loa", headers=_en_tete(SOPHIE)).json()
    assert vue["loueur"] == "DIAC" and vue["terme"] == "2029-03-31"
    assert vue["premier_loyer_cts"] == 300000
    assert vue["engagement_restant_cts"] >= 900000


def test_un_contrat_inutilisable_est_refuse() -> None:
    client = _client()
    reponse = _poster(client, CONTRAT | {"duree_mois": 2})
    assert 400 <= reponse.status_code < 500
    assert client.get(f"/dossiers/{SOPHIE}/loa", headers=_en_tete(SOPHIE)).json() == []
