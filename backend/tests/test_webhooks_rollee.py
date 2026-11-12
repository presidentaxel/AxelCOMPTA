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
from axelcompta.webhooks_rollee import (
    Declaration,
    adresse,
    assurer_secret,
    configurer,
    declarer,
    preparer,
)

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


def _compte(depot: BranchementsMemoire, nom: str, url: str) -> str:
    cree = nouveau(
        depot.lister(T),
        T,
        "rollee",
        "rollee",
        nom,
        {"jeton": "j", "environnement": "sandbox", "url_webhook": url},
    )
    depot.enregistrer([cree], "admin", datetime.now(UTC))
    return cree.id


def test_chaque_compte_declare_son_webhook_vers_sa_propre_adresse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depot = BranchementsMemoire()
    serenity = _compte(depot, "Serenity", "https://api.serenity.fr/")
    maison = _compte(depot, "Maison", "https://api.maison.fr")
    declares: list[tuple[str, str]] = []

    async def faux(client: RolleeHttpClient, url: str, secret: str) -> None:
        await client.aclose()
        declares.append((url, secret))

    monkeypatch.setattr("axelcompta.webhooks_rollee.configurer", faux)
    comptes = {b.id: b for b in depot.lister(T)}
    un = declarer(depot, comptes[serenity], "louis")
    deux = declarer(depot, comptes[maison], "louis")
    assert un.ok and deux.ok
    assert declares[0][0] == f"https://api.serenity.fr/webhooks/rollee/{serenity}"
    assert declares[1][0] == f"https://api.maison.fr/webhooks/rollee/{maison}"
    assert declares[0][1] != declares[1][1]
    assert declares[0][1] not in un.message
    encore = declarer(depot, next(b for b in depot.lister(T) if b.id == serenity), "louis")
    assert encore.ok and declares[2][1] == declares[0][1]


def test_sans_adresse_sur_le_compte_rien_n_est_declare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    depot = BranchementsMemoire()
    cree = nouveau(
        [], T, "rollee", "rollee", "Sans adresse", {"jeton": "j", "environnement": "sandbox"}
    )
    depot.enregistrer([cree], "admin", datetime.now(UTC))
    appele = False

    async def faux(*_args: object) -> None:
        nonlocal appele
        appele = True

    monkeypatch.setattr("axelcompta.webhooks_rollee.configurer", faux)
    resultat = declarer(depot, cree, "louis")
    assert resultat == Declaration(
        False, "Indiquez l'adresse publique de l'API de ce compte, dans ses identifiants."
    )
    assert not appele


def test_preparer_donne_un_secret_par_compte_et_signale_localhost() -> None:
    depot = BranchementsMemoire()
    serenity = _compte(depot, "Serenity", "https://api.serenity.fr")
    maison = _compte(depot, "Maison", "https://api.maison.fr")
    comptes = {b.id: b for b in depot.lister(T)}
    une = preparer(depot, comptes[serenity], "http://127.0.0.1:8001")
    deux = preparer(depot, comptes[maison], "https://api.axelcompta.fr")
    assert not une.joignable and deux.joignable
    assert une.url == f"http://127.0.0.1:8001/webhooks/rollee/{serenity}"
    assert deux.url == f"https://api.axelcompta.fr/webhooks/rollee/{maison}"
    assert une.secret != deux.secret and une.methode == "POST"
    assert "Users" not in une.evenements
    encore = preparer(
        depot, next(b for b in depot.lister(T) if b.id == serenity), "http://localhost:8001"
    )
    assert encore.secret == une.secret
