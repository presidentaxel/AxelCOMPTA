"""AXE-820 : configuration des webhooks Rollee d'un branchement."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from axelcompta.core.ids import TenantId
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
from axelcompta.tenants.branchements import BranchementsMemoire, Modification, modifier, nouveau
from axelcompta.webhooks_rollee import adresse, assurer_secret, configurer

T = TenantId("t")


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def test_le_secret_est_cree_une_fois_et_survit_a_un_changement_de_jeton() -> None:
    depot = BranchementsMemoire()
    cree = nouveau([], T, "rollee", "rollee", "Rollee", {"jeton": "j", "environnement": "sandbox"})
    depot.enregistrer([cree], "admin", datetime.now(UTC))
    garde, secret = assurer_secret(depot, cree)
    _, encore = assurer_secret(depot, garde)
    assert len(secret) == 64 and encore == secret
    nouveau_jeton = modifier(
        depot.lister(T),
        cree.id,
        Modification(parametres={"jeton": "j2", "environnement": "sandbox"}),
    )
    assert nouveau_jeton[-1].parametres()["secret_webhook"] == secret


def test_les_deux_types_sont_declares_avec_tous_leurs_champs() -> None:
    vus: list[httpx.Request] = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        vus.append(requete)
        return httpx.Response(200)

    client = RolleeHttpClient(
        "sandbox",
        "j",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(repondre),
            base_url="https://api.sand.getrollee.com/api/v0.5",
        ),
    )
    url = adresse("https://api.exemple.fr/", "b1")
    asyncio.run(configurer(client, url, "s3cret"))
    assert [r.url.path.rsplit("/", 1)[-1] for r in vus] == ["accounts", "multi_endpoints"]
    assert json.loads(vus[0].content) == {
        "url": "https://api.exemple.fr/webhooks/rollee/b1",
        "method": "POST",
        "enabled": True,
        "secret": "s3cret",
        "headers": {},
    }
