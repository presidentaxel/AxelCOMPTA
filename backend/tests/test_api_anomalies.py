"""Qualifications d'anomalies gardées (AXE-814) : état, historique, reclassement."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()


def _premiere_alerte(client: TestClient) -> tuple[str, dict[str, object]]:
    for dossier in ("DEMO_karim", "DEMO_sophie", "DEMO_yanis"):
        alertes = client.get(f"/dossiers/{dossier}/anomalies", headers=EN_TETE).json()
        if alertes:
            return dossier, alertes[0]
    raise AssertionError("aucune alerte dans la démo")


def _qualifier(
    client: TestClient, dossier: str, alerte: str, decision: str, commentaire: str = ""
) -> int:
    reponse = client.post(
        f"/dossiers/{dossier}/anomalies/{alerte}",
        json={"decision": decision, "commentaire": commentaire},
        headers=EN_TETE,
    )
    return int(reponse.status_code)


def _etat(client: TestClient, dossier: str, alerte: str) -> str:
    alertes = client.get(f"/dossiers/{dossier}/anomalies", headers=EN_TETE).json()
    return str(next(a["etat"] for a in alertes if a["id"] == alerte))


def test_une_alerte_justifiee_ne_repasse_pas_a_ouverte_au_recalcul() -> None:
    client = _client()
    dossier, alerte = _premiere_alerte(client)
    alerte_id = str(alerte["id"])
    assert _qualifier(client, dossier, alerte_id, "en_instruction") == 200
    assert _qualifier(client, dossier, alerte_id, "justifiee", "péage professionnel") == 200

    # Chaque lecture recalcule les alertes : la qualification est retrouvée.
    assert _etat(client, dossier, alerte_id) == "justifiee"
    assert _etat(client, dossier, alerte_id) == "justifiee"
    sujets = client.get("/expert/file", headers=EN_TETE).json()["sujets"]
    assert f"anomalie:{alerte_id}" not in {s["id"] for s in sujets}


def test_l_historique_montre_chaque_changement_avec_son_auteur() -> None:
    client = _client()
    dossier, alerte = _premiere_alerte(client)
    alerte_id = str(alerte["id"])
    _qualifier(client, dossier, alerte_id, "en_instruction")
    _qualifier(client, dossier, alerte_id, "faux_positif")

    historique = client.get(
        f"/dossiers/{dossier}/anomalies/{alerte_id}/historique", headers=EN_TETE
    ).json()

    assert [e["etat"] for e in historique] == ["en_instruction", "faux_positif"]
    assert all(e["acteur"] and e["le"] for e in historique)


def test_l_usage_personnel_propose_un_reclassement_sans_l_ecrire() -> None:
    client = _client()
    dossier, alerte = _premiere_alerte(client)
    alerte_id = str(alerte["id"])
    _qualifier(client, dossier, alerte_id, "en_instruction")
    _qualifier(client, dossier, alerte_id, "usage_personnel")

    sujets = client.get("/expert/file", headers=EN_TETE).json()["sujets"]

    (propose,) = [s for s in sujets if s["id"] == f"reclassement:{alerte_id}"]
    assert propose["compte_suggere"] in {"455", "108"}
    assert propose["compte_actuel"] != propose["compte_suggere"]
    assert propose["nature"] == "anomalie"
