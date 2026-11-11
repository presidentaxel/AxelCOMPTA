"""AXE-818 : test de contrat contre le **sandbox** Rollee, hors CI.

Lancé seulement avec un jeton sandbox (tableau de bord Rollee, Settings →
JWT Token) :

    ROLLEE_JETON_SANDBOX=… python -m pytest -m rollee

Il crée un utilisateur de test et une session Rollee Connect. Avec
`ROLLEE_COMPTE_SANDBOX` (l'identifiant d'un compte relié dans le sandbox, via
le lien de session et n'importe quels identifiants), il lit aussi un mois de
revenus (plateforme `ROLLEE_PLATEFORME_SANDBOX`, Uber par défaut) et
vérifie qu'ils se traduisent sans rejet : c'est ce test qui
confirme l'unité des montants (`UNITE_MONTANTS`).
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta

import pytest

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.rollee import CompteRollee, RolleeHttpClient, lire_revenus
from axelcompta.packs.vtc_demo import charger_plateformes

pytestmark = pytest.mark.rollee

JETON = os.environ.get("ROLLEE_JETON_SANDBOX", "")
COMPTE = os.environ.get("ROLLEE_COMPTE_SANDBOX", "")
PLATEFORME = os.environ.get("ROLLEE_PLATEFORME_SANDBOX", "Uber")


@pytest.fixture
def client() -> RolleeHttpClient:
    if not JETON:
        pytest.skip("ROLLEE_JETON_SANDBOX non défini")
    return RolleeHttpClient("sandbox", JETON)


def test_le_jeton_sandbox_cree_un_utilisateur_et_une_session(client: RolleeHttpClient) -> None:
    async def scenario() -> tuple[dict[str, object], dict[str, object]]:
        try:
            utilisateur = await client.creer_utilisateur({"dossier_id": "TEST_CONTRAT"})
            session = await client.nouvelle_session(str(utilisateur["id"]))
        finally:
            await client.aclose()
        return utilisateur, session

    utilisateur, session = asyncio.run(scenario())
    assert utilisateur["id"]
    assert session.get("link") or session.get("session")


def test_un_mois_de_revenus_sandbox_se_traduit_sans_rejet(client: RolleeHttpClient) -> None:
    if not COMPTE:
        pytest.skip("ROLLEE_COMPTE_SANDBOX non défini")

    async def lire() -> dict[str, object]:
        try:
            fin = date.today()
            return await client.revenus(COMPTE, fin - timedelta(days=31), fin)
        finally:
            await client.aclose()

    reponse = asyncio.run(lire())
    releve = lire_revenus(
        DossierId("TEST"), CompteRollee(COMPTE, PLATEFORME), reponse, charger_plateformes()
    )
    assert releve.rejets == [], [r.motif for r in releve.rejets]
