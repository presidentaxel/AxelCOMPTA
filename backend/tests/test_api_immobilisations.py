"""AXE-802 : le chauffeur déclare son véhicule au registre, la clôture l'amortit."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

SOPHIE = "DEMO_sophie"
ACHAT = f"{SOPHIE}:achat-vehicule"


def _avec_achat(client: TestClient) -> None:
    _ledger_du_client(client).enregistrer(
        Ecriture(
            id=EcritureId(ACHAT),
            dossier_id=DossierId(SOPHIE),
            journal=Journal.BQ,
            date=date(2026, 4, 1),
            libelle="VIR GARAGE TOYOTA",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(30_000_00)),
                LigneEcriture("2182", Sens.DEBIT, Money(30_000_00)),
            ),
        )
    )


def _registre(client: TestClient) -> dict[str, Any]:
    reponse = client.get(f"/dossiers/{SOPHIE}/immobilisations", headers=_en_tete(SOPHIE))
    assert reponse.status_code == 200, reponse.text
    resultat: dict[str, Any] = reponse.json()
    return resultat


def _declarer(client: TestClient, **corps: object) -> Any:
    return client.post(
        f"/dossiers/{SOPHIE}/immobilisations",
        json={
            "ecriture_id": ACHAT,
            "designation": "Toyota Corolla",
            "mise_en_service": "2026-04-01",
            "duree_mois": 60,
        }
        | corps,
        headers=_en_tete(SOPHIE),
    )


def test_un_achat_de_vehicule_est_propose_puis_declare() -> None:
    client = _client()
    _avec_achat(client)
    (propose,) = [b for b in _registre(client)["a_declarer"] if b["ecriture_id"] == ACHAT]
    assert (propose["base_cts"], propose["duree_proposee_mois"]) == (30_000_00, 60)

    reponse = _declarer(client)
    assert reponse.status_code == 200, reponse.text
    (fiche,) = reponse.json()["immobilisations"]
    assert fiche["compte"] == "2182" and fiche["base_cts"] == 30_000_00
    assert not [b for b in reponse.json()["a_declarer"] if b["ecriture_id"] == ACHAT]


def test_declarer_deux_fois_est_refuse() -> None:
    client = _client()
    _avec_achat(client)
    assert _declarer(client).status_code == 200
    assert _declarer(client).status_code == 409


def test_une_operation_qui_n_est_pas_un_achat_est_refusee() -> None:
    client = _client()
    autre = next(
        t["ecriture_id"]
        for t in client.get(f"/dossiers/{SOPHIE}/transactions", headers=_en_tete(SOPHIE)).json()
    )
    reponse = _declarer(client, ecriture_id=autre)
    assert 400 <= reponse.status_code < 500


def test_une_cession_donne_la_plus_value() -> None:
    client = _client()
    _avec_achat(client)
    fiche_id = _declarer(client).json()["immobilisations"][0]["id"]
    reponse = client.post(
        f"/dossiers/{SOPHIE}/immobilisations/{fiche_id}/cession",
        json={"le": "2028-06-30", "prix_cts": 18_000_00},
        headers=_en_tete(SOPHIE),
    )
    assert reponse.status_code == 200, reponse.text
    (fiche,) = reponse.json()["immobilisations"]
    assert (fiche["cede_le"], fiche["plus_ou_moins_value_cts"]) == ("2028-06-30", 1_500_00)
