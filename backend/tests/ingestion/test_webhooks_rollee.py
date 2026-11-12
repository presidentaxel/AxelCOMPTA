"""AXE-820 : signature des webhooks Rollee et lecture des événements."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest

from axelcompta.core.ids import TenantId
from axelcompta.ingestion.webhooks_rollee import (
    EvenementIllisible,
    EvenementsRolleeMemoire,
    lire,
    resume,
    signature_valide,
)

T = TenantId("t")
LE = datetime(2026, 11, 11, tzinfo=UTC)
# Exemple de la doc Rollee (événement de compte, clé `action`).
CONNEXION = {
    "action": "connect_account",
    "data": {"connected": True, "id": "acc-1", "user_id": "user-1"},
}
# Exemple de la doc Rollee (plusieurs comptes, clé `type`).
DONNEES = {
    "type": "update_multi_endpoint",
    "data": {"accounts": [{"user_id": "user-1", "account_id": "a"}, {"user_id": "user-2"}]},
}


def _signe(secret: str, corps: bytes) -> bytes:
    return hmac.new(secret.encode(), corps, hashlib.sha512).digest()


def test_la_signature_se_verifie_en_hexadecimal_ou_base64() -> None:
    corps = json.dumps(CONNEXION).encode()
    brute = _signe("s3cret", corps)
    assert signature_valide("s3cret", corps, brute.hex())
    assert signature_valide("s3cret", corps, base64.b64encode(brute).decode())
    assert signature_valide("s3cret", corps, "sha512=" + brute.hex())
    assert not signature_valide("autre", corps, brute.hex())
    assert not signature_valide("s3cret", corps + b" ", brute.hex())
    assert not signature_valide("", corps, brute.hex()) and not signature_valide("s", corps, None)


def test_le_type_se_lit_sous_action_ou_type_et_les_users_aussi() -> None:
    compte = lire(json.dumps(CONNEXION).encode(), T, "b1", LE)
    donnees = lire(json.dumps(DONNEES).encode(), T, "b1", LE)
    assert (compte.type, compte.users) == ("connect_account", ("user-1",))
    assert (donnees.type, donnees.users) == ("update_multi_endpoint", ("user-1", "user-2"))
    with pytest.raises(EvenementIllisible):
        lire(b"pas du json", T, "b1", LE)
    with pytest.raises(EvenementIllisible):
        lire(b'{"data": {}}', T, "b1", LE)


def test_un_webhook_rejoue_n_est_garde_qu_une_fois() -> None:
    depot = EvenementsRolleeMemoire()
    corps = json.dumps(CONNEXION).encode()
    assert depot.garder(lire(corps, T, "b1", LE))
    assert not depot.garder(lire(corps, T, "b1", LE))
    (attente,) = depot.a_traiter(T, 10)
    depot.marquer_traite(attente.id, "ok", LE)
    assert depot.a_traiter(T, 10) == []
    assert resume(["a", "b"]) == "2 événements Rollee traités"
