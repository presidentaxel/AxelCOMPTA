"""AXE-818 : test de contrat contre le **sandbox** Rollee, hors CI.

Le jeton est celui d'un branchement Rollee dont l'environnement est
`sandbox` (Intégrations), pas une variable d'environnement :

    python -m pytest -m rollee

Il crée un utilisateur de test et une session Rollee Connect. S'il trouve
un compte déjà relié sur ce sandbox, il lit aussi un mois de revenus et
vérifie qu'ils se traduisent sans rejet : c'est ce test qui confirme
l'unité des montants (`UNITE_MONTANTS`).
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.rollee import CompteRollee, RolleeHttpClient, lire_revenus
from axelcompta.packs.vtc_demo import charger_plateformes
from axelcompta.plateformes_rollee import TYPE_ROLLEE
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.postgres import PostgresDossierRepository

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

pytestmark = pytest.mark.rollee


def _client() -> RolleeHttpClient:
    if not os.environ.get("DATABASE_URL") or not os.environ.get("AXELCOMPTA_CLE_INTEGRATIONS"):
        pytest.skip("branchement Rollee sandbox : base ou clé absente")
    engine = engine_depuis_env()
    depot = PostgresBranchements(engine)
    for tenant in PostgresDossierRepository(engine).lister_tenants():
        for branchement in depot.lister(tenant.id):
            if branchement.type != TYPE_ROLLEE or not branchement.actif:
                continue
            parametres = branchement.parametres()
            if parametres.get("environnement") == "sandbox" and parametres.get("jeton"):
                return RolleeHttpClient.depuis_parametres(parametres)
    pytest.skip("aucun branchement Rollee sandbox")


@pytest.fixture
def client() -> RolleeHttpClient:
    return _client()


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
    async def lire() -> tuple[str, str, dict[str, object]] | None:
        try:
            for utilisateur in await client.utilisateurs():
                identifiant = str(utilisateur.get("id") or "")
                if not identifiant:
                    continue
                for compte in await client.comptes(identifiant):
                    if not (compte.get("connected") and compte.get("id") and compte.get("name")):
                        continue
                    compte_id, nom = str(compte["id"]), str(compte["name"])
                    fin = date.today()
                    reponse = await client.revenus(compte_id, fin - timedelta(days=31), fin)
                    return compte_id, nom, reponse
            return None
        finally:
            await client.aclose()

    trouve = asyncio.run(lire())
    if trouve is None:
        pytest.skip("aucun compte Rollee relié dans le sandbox")
    compte_id, nom, reponse = trouve
    releve = lire_revenus(
        DossierId("TEST"), CompteRollee(compte_id, nom), reponse, charger_plateformes()
    )
    assert releve.rejets == [], [r.motif for r in releve.rejets]
