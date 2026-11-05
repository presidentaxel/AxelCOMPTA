"""Routes des tags (AXE-829) : pose, exclusion des traitements, droits."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()


def _client(role: str = "admin") -> TestClient:
    return _client_et_stubs(role)[0]


def _un_dossier(client: TestClient) -> str:
    return str(client.get("/dossiers", headers=EN_TETE).json()[0]["dossier_id"])


def _dossiers_de_la_file(client: TestClient) -> set[str]:
    sujets = client.get("/expert/file", headers=EN_TETE).json()["sujets"]
    return {s["dossier_id"] for s in sujets}


def test_les_tags_proposes_et_les_traitements_sont_lus() -> None:
    corps = _client().get("/tags", headers=EN_TETE).json()
    assert {"chauffeur", "societe_du_gestionnaire", "hors_perimetre", "test"} <= {
        t["nom"] for t in corps["tags"]
    }
    assert "societe_du_gestionnaire" in corps["exclusions"]["expert"]
    assert "synchro" in corps["traitements"]


def test_une_societe_du_gestionnaire_sort_du_mode_expert_et_revient() -> None:
    client = _client()
    dossier = _un_dossier(client)
    assert dossier in _dossiers_de_la_file(client)
    route = "/tags/societe_du_gestionnaire/dossiers"

    assert client.post(route, json={"dossier_ids": [dossier]}, headers=EN_TETE).status_code == 204

    assert dossier not in _dossiers_de_la_file(client)
    vue = next(
        d for d in client.get("/dossiers", headers=EN_TETE).json() if d["dossier_id"] == dossier
    )
    assert vue["tags"] == ["societe_du_gestionnaire"]
    assert vue["exclu_compteurs"] is True

    client.post(route, json={"dossier_ids": [dossier], "pose": False}, headers=EN_TETE)
    assert dossier in _dossiers_de_la_file(client)


def test_un_reglage_peut_garder_un_tag_dans_le_mode_expert() -> None:
    client = _client()
    dossier = _un_dossier(client)
    client.post(
        "/tags/societe_du_gestionnaire/dossiers", json={"dossier_ids": [dossier]}, headers=EN_TETE
    )
    reponse = client.put("/tags/exclusions/expert", json={"tags": []}, headers=EN_TETE)
    assert reponse.status_code == 200
    assert reponse.json()["exclusions"]["expert"] == []
    # Les anomalies ont leur propre réglage : ce dossier n'en a pas d'autres.
    assert dossier not in _dossiers_de_la_file(client)

    client.put("/tags/exclusions/anomalies", json={"tags": []}, headers=EN_TETE)
    assert dossier in _dossiers_de_la_file(client)


def test_creer_un_tag_puis_le_poser() -> None:
    client = _client()
    dossier = _un_dossier(client)
    reponse = client.post("/tags", json={"nom": "Flotte Nord"}, headers=EN_TETE)
    assert "flotte_nord" in {t["nom"] for t in reponse.json()["tags"]}
    pose = client.post(
        "/tags/flotte_nord/dossiers", json={"dossier_ids": [dossier]}, headers=EN_TETE
    )
    assert pose.status_code == 204


def test_les_erreurs_de_saisie_sont_des_400() -> None:
    client = _client()
    dossier = _un_dossier(client)
    assert client.post("/tags", json={"nom": "é"}, headers=EN_TETE).status_code == 400
    inconnu = client.post(
        "/tags/inconnu/dossiers", json={"dossier_ids": [dossier]}, headers=EN_TETE
    )
    assert inconnu.status_code == 400
    assert (
        client.put("/tags/exclusions/inventé", json={"tags": []}, headers=EN_TETE).status_code
        == 400
    )


def test_le_role_lecture_ne_pose_pas_de_tag() -> None:
    client = _client(role="lecture")
    dossier = _un_dossier(client)
    reponse = client.post("/tags/test/dossiers", json={"dossier_ids": [dossier]}, headers=EN_TETE)
    assert reponse.status_code == 403
    assert client.post("/tags", json={"nom": "x_y"}, headers=EN_TETE).status_code == 403


def test_un_dossier_d_un_autre_portefeuille_est_introuvable() -> None:
    client = _client()
    dossier = _un_dossier(client)
    autre = _en_tete_gestionnaire(tenant_id="AUTRE_TENANT")
    reponse = client.post("/tags/test/dossiers", json={"dossier_ids": [dossier]}, headers=autre)
    assert reponse.status_code == 404
