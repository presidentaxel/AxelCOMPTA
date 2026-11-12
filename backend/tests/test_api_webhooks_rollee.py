"""AXE-820 : la route publique du webhook Rollee."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from axelcompta.demo_api import get_reception_rollee
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
from tests.test_plateformes_rollee import _avec_secret, _Reception, _signer


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _client(reception: _Reception) -> TestClient:
    client = _client_et_stubs()[0]
    client.app.dependency_overrides[get_reception_rollee] = lambda: reception  # type: ignore[attr-defined]
    return client


def test_sans_compte_seule_la_signature_ouvre_la_porte() -> None:
    reception = _Reception(_avec_secret())
    client = _client(reception)
    corps = json.dumps({"action": "connect_account", "data": {"user_id": "u"}}).encode()
    refuse = client.post("/webhooks/rollee/b1", content=corps, headers={"X-Signature": "x"})
    accepte = client.post(
        "/webhooks/rollee/b1", content=corps, headers={"X-Signature": _signer(corps)}
    )
    rejoue = client.post(
        "/webhooks/rollee/b1", content=corps, headers={"X-Signature": _signer(corps)}
    )
    assert refuse.status_code == 401
    assert (accepte.status_code, accepte.json()) == (200, {"statut": "garde"})
    assert rejoue.json() == {"statut": "deja_recu"} and len(reception.demandes) == 1


def test_un_branchement_inconnu_repond_404() -> None:
    reponse = _client(_Reception(None)).post("/webhooks/rollee/x", content=b"{}")
    assert reponse.status_code == 404
