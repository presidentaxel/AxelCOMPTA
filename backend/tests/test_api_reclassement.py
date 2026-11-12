"""AXE-420 : la décision du chauffeur s'écrit au grand livre (OD de reclassement)."""

from __future__ import annotations

from collections import Counter

import pytest
from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.workflow.reclassement import source_du_reclassement
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _client_expert,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
    _premiere_a_trancher,
)

SOPHIE = "DEMO_sophie"


def _decider(client: TestClient, ecriture_id: str, categorie: str, route: str = "decision") -> None:
    reponse = client.post(
        f"/dossiers/{SOPHIE}/transactions/{ecriture_id}/{route}",
        json={"categorie": categorie},
        headers=_en_tete(SOPHIE),
    )
    assert reponse.status_code == 200, reponse.text


def _reclassements(client: TestClient, ecriture_id: str) -> list[Ecriture]:
    brut = _ledger_du_client(client).grand_livre(DossierId(SOPHIE))
    return [e for e in brut if source_du_reclassement(e.id) == ecriture_id]


def _soldes(ecritures: tuple[Ecriture, ...]) -> Counter[str]:
    soldes: Counter[str] = Counter()
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            soldes[ligne.compte] += (1 if ligne.sens is Sens.DEBIT else -1) * ligne.montant.centimes
    return soldes


def test_une_decision_ecrit_un_reclassement_en_base() -> None:
    client = _client()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)

    _decider(client, ecriture_id, "usage_personnel")

    (reclassement,) = _reclassements(client, ecriture_id)
    assert reclassement.id == f"{ecriture_id}:decision-1"
    assert {ligne.compte for ligne in reclassement.lignes} == {"455", "471"}
    # L'écran montre l'opération sur 455, sans ligne de reclassement à part.
    vues = client.get(f"/dossiers/{SOPHIE}/transactions", headers=_en_tete(SOPHIE)).json()
    assert next(t for t in vues if t["ecriture_id"] == ecriture_id)["compte"] == "455"
    assert not any(":decision-" in t["ecriture_id"] for t in vues)


def test_le_fec_contient_le_reclassement() -> None:
    client = _client()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)
    _decider(client, ecriture_id, "usage_personnel")

    fec = client.get(f"/dossiers/{SOPHIE}/fec.txt", headers=_en_tete(SOPHIE))

    assert fec.status_code == 200
    assert "Reclassement" in fec.text


def test_une_correction_ecrit_un_second_reclassement() -> None:
    client = _client()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)
    _decider(client, ecriture_id, "usage_personnel")
    _decider(client, ecriture_id, "carburant", route="correction")

    premier, second = _reclassements(client, ecriture_id)
    assert premier.lignes[0].compte == "455"
    assert second.id.endswith(":decision-2")
    # AXE-831 : le carburant sépare sa TVA déductible estimée.
    assert {ligne.compte for ligne in second.lignes} == {"455", "6061", "44566"}
    brut = _ledger_du_client(client).grand_livre(DossierId(SOPHIE))
    operation = tuple(e for e in brut if e.id == ecriture_id) + (premier, second)
    soldes = _soldes(operation)
    assert soldes["471"] == 0 and soldes["455"] == 0  # tout est passé en 6061
    assert soldes["6061"] != 0
    assert soldes["44566"] * 6 == pytest.approx(soldes["6061"] + soldes["44566"], abs=6)


def test_l_imputation_de_l_expert_contre_passe_aussi_le_reclassement() -> None:
    client = _client_expert()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)
    _decider(client, ecriture_id, "usage_personnel")
    avant = _soldes(_ledger_du_client(client).grand_livre(DossierId(SOPHIE)))

    reponse = client.post(
        "/expert/imputations",
        json={
            "dossier_id": SOPHIE,
            "ecriture_id": ecriture_id,
            "compte": "6061",
            "motif": "Plein de la flotte",
        },
        headers=_en_tete_gestionnaire(),
    )

    assert reponse.status_code == 200, reponse.text
    apres = _soldes(_ledger_du_client(client).grand_livre(DossierId(SOPHIE)))
    montant = avant["455"] - apres["455"]
    assert montant > 0  # 455 n'est plus chargé de cette opération
    assert apres["6061"] - avant["6061"] == montant  # elle est en 6061, une seule fois
    assert apres["471"] == avant["471"]


def test_une_depense_carburant_montre_sa_tva_estimee() -> None:
    """AXE-831 : le chauffeur voit la TVA estimée d'une dépense tranchée."""
    client = _client()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)
    _decider(client, ecriture_id, "carburant")
    vues = client.get(f"/dossiers/{SOPHIE}/transactions", headers=_en_tete(SOPHIE)).json()
    vue = next(t for t in vues if t["ecriture_id"] == ecriture_id)
    assert vue["compte"] == "6061"
    assert vue["tva_estimee_cts"] and vue["tva_estimee_cts"] > 0
