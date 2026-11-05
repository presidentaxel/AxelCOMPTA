from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import cast

import httpx
import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.providers.digifactory import (
    DigifactoryAuthError,
    DigifactoryHttpClient,
    DigifactoryProvider,
    chauffeur_peut_connecter_sa_banque,
    fenetres_mensuelles,
    parser_lot,
    parser_transactions,
)
from axelcompta.tenants.models import Dossier

DOSSIER = DossierId("d1")
DEPUIS, JUSQUA = date(2026, 1, 1), date(2026, 12, 31)


def test_filtre_deleted_et_future() -> None:
    payload = {
        "acc_1": [
            {
                "id": "tx1",
                "amount": 10.0,
                "date": "2026-06-01",
                "updated_at": "2026-06-01T00:00:00",
                "deleted": False,
                "future": False,
                "provider_description": "OK",
            },
            {
                "id": "tx2",
                "amount": 20.0,
                "date": "2026-06-02",
                "updated_at": "2026-06-02T00:00:00",
                "deleted": True,
                "future": False,
                "provider_description": "SUPPRIME",
            },
            {
                "id": "tx3",
                "amount": 30.0,
                "date": "2099-01-01",
                "updated_at": "2026-06-02T00:00:00",
                "deleted": False,
                "future": True,
                "provider_description": "PROJETE",
            },
        ]
    }
    transactions = parser_transactions(payload, DOSSIER, DEPUIS, JUSQUA)
    assert [t.libelle for t in transactions] == ["OK"]


def test_deduplique_par_id_en_gardant_le_plus_recent() -> None:
    payload = {
        "acc_1": [
            {
                "id": "tx1",
                "amount": 10.0,
                "date": "2026-06-01",
                "updated_at": "2026-06-01T00:00:00",
                "deleted": False,
                "future": False,
                "provider_description": "ancien montant",
            },
            {
                "id": "tx1",
                "amount": 15.0,
                "date": "2026-06-01",
                "updated_at": "2026-06-02T00:00:00",
                "deleted": False,
                "future": False,
                "provider_description": "montant corrigé",
            },
        ]
    }
    transactions = parser_transactions(payload, DOSSIER, DEPUIS, JUSQUA)
    assert len(transactions) == 1
    assert transactions[0].montant_cts == 15_00
    assert transactions[0].libelle == "montant corrigé"


def test_ne_depend_pas_de_la_cle_du_payload() -> None:
    # doc 16 §3.1 : la clé peut ne pas être l'accountId réel, seul le champ
    # account_id sur la transaction (ici absent, tout aussi valide) compte.
    payload = {
        "Bourso": [
            {
                "id": "tx1",
                "amount": 10.0,
                "date": "2026-06-01",
                "updated_at": "2026-06-01T00:00:00",
                "deleted": False,
                "future": False,
                "provider_description": "OK",
            }
        ]
    }
    assert len(parser_transactions(payload, DOSSIER, DEPUIS, JUSQUA)) == 1


def test_provider_utilise_la_fixture_par_defaut() -> None:
    transactions = asyncio.run(
        DigifactoryProvider().fetch_transactions(TenantId("t1"), DOSSIER, DEPUIS, JUSQUA)
    )
    # 1 transaction valide sur les 3 de la fixture (deleted + future exclues)
    assert len(transactions) == 1
    assert transactions[0].montant_cts == 848_00


def test_health_sans_client_reel_signale_les_fixtures() -> None:
    sante = asyncio.run(DigifactoryProvider().health())
    assert sante.ok is False
    assert "fixtures" in sante.message


def test_accepte_le_format_reel_dict_indexe_par_transaction_id() -> None:
    # doc 16 §3.1 documentait une liste par compte ; le payload réel
    # (vérifié 2026-09-11) est un dict {transactionId: transaction} — les
    # valeurs ci-dessous sont fabriquées, pas de vraies données.
    payload = {
        "acc_1": {
            "tx1": {
                "id": "tx1",
                "amount": 10.0,
                "date": "2026-06-01 00:00:00",
                "updated_at": "2026-06-01 00:00:00",
                "deleted": False,
                "future": False,
                "provider_description": "FORMAT REEL",
            }
        }
    }
    transactions = parser_transactions(payload, DOSSIER, DEPUIS, JUSQUA)
    assert [t.libelle for t in transactions] == ["FORMAT REEL"]


def _client_mocke(handler: httpx.MockTransport) -> DigifactoryHttpClient:
    return DigifactoryHttpClient(
        "https://entrepreneur.digifactory.fr/api/bridge",
        "un-token-de-test",
        client=httpx.AsyncClient(
            transport=handler,
            base_url="https://entrepreneur.digifactory.fr/api/bridge",
            headers={"accept": "*/*", "X_DIGI_TOKEN": "un-token-de-test"},
        ),
    )


def test_http_client_envoie_bien_x_digi_token_pas_authorization_bearer() -> None:
    # Non-régression directe de la cause du blocage 2026-09-01/09-11 (doc 16
    # §2, §7) : si un jour quelqu'un « corrige » ça vers Authorization, ce
    # test casse.
    recu: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recu.update(request.headers)
        return httpx.Response(200, json={})

    client = _client_mocke(httpx.MockTransport(handler))
    asyncio.run(client.categories())
    assert recu.get("x_digi_token") == "un-token-de-test"
    assert "authorization" not in recu


def test_http_client_401_leve_digifactoryautherror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"exception": "UnauthorizedException", "code": 401}},
        )

    client = _client_mocke(httpx.MockTransport(handler))
    with pytest.raises(DigifactoryAuthError):
        asyncio.run(client.categories())


def test_health_avec_client_reel_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"1": {"id": "1", "name": "Cat"}})

    provider = DigifactoryProvider(client_reel=_client_mocke(httpx.MockTransport(handler)))
    sante = asyncio.run(provider.health())
    assert sante.ok is True


def test_health_avec_client_reel_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": 401}})

    provider = DigifactoryProvider(client_reel=_client_mocke(httpx.MockTransport(handler)))
    sante = asyncio.run(provider.health())
    assert sante.ok is False
    assert "401" in sante.message


def test_reponse_vide_est_un_lot_vide() -> None:
    assert parser_lot([], DOSSIER).transactions == ()
    assert parser_lot({}, DOSSIER).transactions == ()


def test_fenetres_couvrent_le_mois_de_depart_jusqu_au_mois_suivant() -> None:
    fenetres = fenetres_mensuelles(date(2025, 12, 15), date(2026, 1, 2))
    assert fenetres == (
        (datetime(2025, 12, 15), datetime(2025, 12, 31, 23, 59, 59)),
        (datetime(2026, 1, 1), datetime(2026, 1, 2, 23, 59, 59)),
    )


class _ClientMensuel:
    def __init__(self) -> None:
        self.appels: list[tuple[datetime | None, datetime | None, datetime | None]] = []

    async def transactions(
        self,
        contact_nr: str | int,
        since: datetime | None = None,
        debut: datetime | None = None,
        fin: datetime | None = None,
    ) -> list[object]:
        self.appels.append((since, debut, fin))
        return []


def _dossier() -> Dossier:
    return Dossier(
        id=DOSSIER,
        tenant_id=TenantId("t"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="D",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 15),
        contact_nr="9",
    )


def test_contact_digifactory_empeche_de_connecter_sa_banque() -> None:
    """Un dossier branché (contact_nr) ne propose pas une connexion chauffeur,
    même si son mode était encore chauffeur_direct."""
    direct = _dossier()
    assert chauffeur_peut_connecter_sa_banque(direct) is False
    sans_contact = Dossier(
        id=DOSSIER,
        tenant_id=TenantId("t"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="D",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 15),
        mode_acces_bancaire="chauffeur_direct",
    )
    assert chauffeur_peut_connecter_sa_banque(sans_contact) is True


def test_premier_chargement_decoupe_par_mois_puis_le_suivant_utilise_since() -> None:
    client = _ClientMensuel()
    provider = DigifactoryProvider(client_reel=cast(DigifactoryHttpClient, client))
    lot = asyncio.run(provider.lire_lot(_dossier(), None))
    assert lot.transactions == ()
    assert len(client.appels) == len(fenetres_mensuelles(date(2026, 1, 15), date.today()))
    assert all(since is None and debut is not None for since, debut, _fin in client.appels)
    client.appels.clear()
    asyncio.run(provider.lire_lot(_dossier(), datetime(2026, 9, 1, 8, 0, 0)))
    assert client.appels == [(datetime(2026, 9, 1, 8, 0, 0), None, None)]


def test_le_compte_bancaire_vient_du_champ_account_id() -> None:
    """AXE-832 : chaque transaction porte son compte, pour le sous-compte 512x."""
    ligne = {
        "date": "2026-06-01",
        "updated_at": "2026-06-01T00:00:00",
        "deleted": False,
        "future": False,
        "provider_description": "TOTAL",
    }
    payload = {
        "cle_quelconque": [
            {**ligne, "id": "a", "amount": -10.0, "account_id": 67078894},
            {**ligne, "id": "b", "amount": -12.0, "account_id": "  "},
            {**ligne, "id": "c", "amount": -14.0},
        ]
    }
    par_id = {str(t.id): t for t in parser_transactions(payload, DOSSIER, DEPUIS, JUSQUA)}
    assert par_id["a"].compte_bancaire == "67078894"
    assert par_id["b"].compte_bancaire is None
    assert par_id["c"].compte_bancaire is None
