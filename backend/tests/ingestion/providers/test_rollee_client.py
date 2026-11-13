"""AXE-818 : client Rollee (jeton, renouvellement, limites) et traduction des
revenus en `PlatformSettlement`.

Les réponses ci-dessous sont construites d'après le schéma publié par
Rollee (developers.getrollee.com, lu le 2026-11-11), qui ne donne aucun
exemple : ce ne sont pas des réponses réelles. Le test de contrat
(`test_rollee_contrat.py`, jeton sandbox) les confronte au vrai service.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import httpx
import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.providers.rollee import (
    CompteRollee,
    RevenuIllisible,
    RolleeAuthError,
    RolleeHttpClient,
    RolleeIndisponible,
    RolleeProvider,
    centimes,
    fin_de_periode,
    lire_revenus,
    premiere_fiche,
)
from axelcompta.packs.vtc_demo import charger_plateformes

D = DossierId("DIGI_1")
PLATEFORMES = charger_plateformes()
SEMAINE_UBER = {
    "time_period_start_date": "2026-10-05",
    "time_period_type": "weekly",
    "gross_earnings": 1040.0,
    "platform_fee": 180.5,
    "other_fees": 11.5,
    "net_amount": 848.0,
    "payouts": 848.0,
    "currency": "EUR",
}


def _client(
    reponses: list[httpx.Response], vus: list[httpx.Request], jetons: list[str] | None = None
) -> RolleeHttpClient:
    file = list(reponses)

    def repondre(requete: httpx.Request) -> httpx.Response:
        vus.append(requete)
        return file.pop(0)

    async def sans_attendre(_s: float) -> None:
        return None

    transport = httpx.MockTransport(repondre)
    return RolleeHttpClient(
        "sandbox",
        "jeton-1",
        client=httpx.AsyncClient(
            transport=transport, base_url="https://api.sand.getrollee.com/api/v0.5"
        ),
        sur_nouveau_jeton=(jetons.append if jetons is not None else None),
        attendre=sans_attendre,
    )


def test_le_jeton_part_en_bearer_et_les_dates_en_timestamps() -> None:
    vus: list[httpx.Request] = []
    client = _client([httpx.Response(200, json={"data": []})], vus)
    asyncio.run(client.revenus("acc-1", date(2026, 10, 1), date(2026, 10, 31)))
    (requete,) = vus
    assert requete.headers["Authorization"] == "Bearer jeton-1"
    assert requete.url.path.endswith("/accounts/acc-1/income")
    assert requete.url.params["start_date"] == "1790812800"  # 2026-10-01 00:00 UTC


def test_un_401_renouvelle_le_jeton_une_fois_et_le_garde() -> None:
    vus: list[httpx.Request] = []
    jetons: list[str] = []
    client = _client(
        [
            httpx.Response(401),
            httpx.Response(200, json={"token": "jeton-2"}),
            httpx.Response(200, json=[]),
        ],
        vus,
        jetons,
    )
    assert asyncio.run(client.comptes("user-1")) == []
    assert jetons == ["jeton-2"]
    assert vus[-1].headers["Authorization"] == "Bearer jeton-2"


def test_un_401_apres_renouvellement_leve_une_erreur_d_authentification() -> None:
    client = _client(
        [httpx.Response(401), httpx.Response(200, json={"token": "j2"}), httpx.Response(401)], []
    )
    with pytest.raises(RolleeAuthError):
        asyncio.run(client.comptes("user-1"))


def test_429_puis_succes_et_5xx_persistant() -> None:
    vus: list[httpx.Request] = []
    client = _client([httpx.Response(429), httpx.Response(200, json=[])], vus)
    assert asyncio.run(client.comptes("u")) == [] and len(vus) == 2
    panne = _client([httpx.Response(503)] * 3, [])
    with pytest.raises(RolleeIndisponible):
        asyncio.run(panne.comptes("u"))


def test_creer_un_utilisateur_envoie_le_dossier_en_metadonnee() -> None:
    vus: list[httpx.Request] = []
    client = _client([httpx.Response(200, json={"id": "user-1", "link": "https://connect"})], vus)
    utilisateur = asyncio.run(client.creer_utilisateur({"dossier_id": "DIGI_1"}))
    assert utilisateur["id"] == "user-1"
    assert json.loads(vus[0].content) == {"metadata": {"dossier_id": "DIGI_1"}}


def test_centimes_sans_arrondi() -> None:
    assert centimes(848, "x") == 848_00 and centimes("12.3", "x") == 12_30
    assert centimes(None, "x") == 0
    with pytest.raises(RevenuIllisible):
        centimes(1.005, "x")
    with pytest.raises(RevenuIllisible):
        centimes("abc", "x")


def test_fin_de_periode() -> None:
    assert fin_de_periode(date(2026, 10, 5), "weekly") == date(2026, 10, 11)
    assert fin_de_periode(date(2026, 2, 1), "monthly") == date(2026, 2, 28)
    with pytest.raises(RevenuIllisible):
        fin_de_periode(date(2026, 2, 1), "custom")


def test_une_semaine_uber_devient_un_settlement_brut_moins_frais_egal_verse() -> None:
    releve = lire_revenus(D, CompteRollee("acc-1", "Uber"), {"data": [SEMAINE_UBER]}, PLATEFORMES)
    (s,) = releve.settlements
    assert (s.platform, s.commission_tva_regime) == ("uber", "france_20")
    assert (s.gross_earnings_cts, s.commission_cts, s.net_payout_cts) == (1_040_00, 192_00, 848_00)
    assert (s.period_start, s.period_end, s.payout_date) == (
        date(2026, 10, 5),
        date(2026, 10, 11),
        date(2026, 10, 11),
    )
    assert releve.rejets == []


@pytest.mark.parametrize(
    ("changement", "motif"),
    [
        ({"payouts": 900.0}, "écart"),
        ({"currency": "GBP"}, "devise"),
        ({"time_period_type": "custom"}, "custom"),
        ({"gross_earnings": 1040.001}, "décimales"),
    ],
)
def test_une_periode_incoherente_part_en_quarantaine_avec_la_raison(
    changement: dict[str, Any], motif: str
) -> None:
    revenu = {**SEMAINE_UBER, **changement}
    releve = lire_revenus(D, CompteRollee("acc-1", "Uber"), {"data": [revenu]}, PLATEFORMES)
    assert releve.settlements == []
    (rejet,) = releve.rejets
    assert motif in rejet.motif and rejet.payload == revenu


def test_une_plateforme_inconnue_du_pack_est_mise_de_cote() -> None:
    releve = lire_revenus(D, CompteRollee("acc-9", "Heetch"), {"data": [SEMAINE_UBER]}, PLATEFORMES)
    assert releve.settlements == [] and "Heetch" in releve.rejets[0].motif


def test_le_provider_lit_chaque_compte_connecte_du_dossier() -> None:
    vus: list[httpx.Request] = []
    bolt = {
        **SEMAINE_UBER,
        "gross_earnings": 500.0,
        "platform_fee": 50.0,
        "other_fees": 0,
        "payouts": 450.0,
    }
    client = _client(
        [
            httpx.Response(200, json={"data": [SEMAINE_UBER]}),
            httpx.Response(200, json={"data": [bolt]}),
        ],
        vus,
    )
    comptes = (
        CompteRollee("acc-uber", "Uber"),
        CompteRollee("acc-off", "Heetch", connecte=False),
        CompteRollee("acc-bolt", "Bolt"),
    )
    provider = RolleeProvider(
        client=client, comptes_du_dossier=lambda _d: comptes, plateformes=PLATEFORMES
    )
    settlements = asyncio.run(
        provider.fetch_platform_settlements(TenantId("t"), D, date(2026, 10, 1), date(2026, 10, 31))
    )
    assert [(s.platform, s.net_payout_cts) for s in settlements] == [
        ("uber", 848_00),
        ("bolt", 450_00),
    ]
    assert [r.url.path.split("/")[-2] for r in vus] == ["acc-uber", "acc-bolt"]


def test_health_renouvelle_le_jeton() -> None:
    jetons: list[str] = []
    client = _client([httpx.Response(200, json={"token": "neuf"})], [], jetons)
    sante = asyncio.run(RolleeProvider(client=client, comptes_du_dossier=lambda _d: ()).health())
    assert sante.ok and jetons == ["neuf"]


def test_tous_les_users_sont_lus_page_apres_page() -> None:
    """AXE-911 : `next_page_link` jusqu'à la dernière page, en lecture seule."""
    vus: list[httpx.Request] = []
    suivante = "https://api.sand.getrollee.com/api/v0.5/users?page=2"
    client = _client(
        [
            httpx.Response(200, json={"data": [{"id": "u1"}], "next_page_link": suivante}),
            httpx.Response(200, json={"data": [{"id": "u2", "metadata": {}}]}),
        ],
        vus,
    )
    assert [u["id"] for u in asyncio.run(client.utilisateurs())] == ["u1", "u2"]
    assert [r.method for r in vus] == ["GET", "GET"]
    assert vus[1].url.params["page"] == "2"


# AXE-917 : forme réelle des réponses (lue le 14/11, valeurs inventées).
PROFIL_ROLLEE = {
    "account_id": "acc-1",
    "connected": True,
    "size": 1,
    "user_id": "u-1",
    "data": [
        {
            "first_name": "Élodie",
            "last_name": "Martin",
            "full_name": "Élodie Martin",
            "email": "e@m.fr",
            "phone": "+33600000000",
        }
    ],
}


def test_profil_et_iban_d_un_compte_sont_lus_dans_leur_enveloppe() -> None:
    vus: list[httpx.Request] = []
    client = _client(
        [
            httpx.Response(200, json=PROFIL_ROLLEE),
            httpx.Response(
                200,
                json={"account_id": "acc-1", "connected": True, "data": [{"iban": "FR76..."}]},
            ),
        ],
        vus,
    )
    profil = asyncio.run(client.profil("acc-1"))
    assert (profil["first_name"], profil["email"]) == ("Élodie", "e@m.fr")
    assert asyncio.run(client.coordonnees_bancaires("acc-1"))["iban"] == "FR76..."
    assert [r.url.path.rsplit("/", 1)[-1] for r in vus] == ["profile", "banking_info"]


def test_bolt_sans_iban_rend_une_fiche_vide_et_uber_en_400_leve() -> None:
    client = _client(
        [
            httpx.Response(200, json={"account_id": "a", "connected": True, "data": []}),
            httpx.Response(400, json={"detail": "not supported"}),
        ],
        [],
    )
    assert asyncio.run(client.coordonnees_bancaires("bolt")) == {}
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.coordonnees_bancaires("uber"))


def test_premiere_fiche_accepte_une_reponse_sans_enveloppe() -> None:
    assert premiere_fiche({"first_name": "A"}) == {"first_name": "A"}
    assert premiere_fiche({"data": {"iban": "X"}}) == {"iban": "X"}
    assert premiere_fiche({"data": None}) == {}
    assert premiere_fiche(None) == {}


def test_des_401_simultanes_ne_renouvellent_le_jeton_qu_une_fois() -> None:
    renouvellements: list[str] = []
    jetons: list[str] = []

    async def repondre(requete: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.01)  # les appels se croisent
        if requete.url.path.endswith("/token/refresh"):
            renouvellements.append(requete.headers["Authorization"])
            return httpx.Response(200, json={"token": "jeton-2"})
        if requete.headers["Authorization"] == "Bearer jeton-1":
            return httpx.Response(401)
        return httpx.Response(200, json=[])

    client = RolleeHttpClient(
        "sandbox",
        "jeton-1",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(repondre),
            base_url="https://api.sand.getrollee.com/api/v0.5",
        ),
        sur_nouveau_jeton=jetons.append,
    )

    async def plusieurs() -> list[list[dict[str, Any]]]:
        return list(await asyncio.gather(*(client.comptes(f"u-{i}") for i in range(5))))

    assert asyncio.run(plusieurs()) == [[]] * 5
    assert renouvellements == ["Bearer jeton-1"]
    assert jetons == ["jeton-2"]
