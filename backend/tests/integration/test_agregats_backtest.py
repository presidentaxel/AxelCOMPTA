"""Backtest des agrégats du portefeuille (AXE-566) : ce que la liste affiche
doit toujours être ce que le calcul d'avant aurait donné, et chaque écriture
ne doit faire recalculer que son dossier.

Tout est réel sauf Supabase et le stockage de justificatifs : Postgres avec
les migrations (donc les triggers), l'API sous le rôle `axelcompta_web` (donc
la RLS), les vraies routes pour les écritures de l'API, et une écriture
directe du propriétaire pour ce que posent la synchro Digifactory et les
scripts, qui ne passent par aucune route.

La référence est `_resume`, le calcul d'avant, lu avec le propriétaire de la
base : elle ne touche jamais à `agregats_dossier`.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url

import axelcompta.demo_api as demo_api
import axelcompta.demo_auth as demo_auth
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.demo_comptes_memory import InMemoryCompteRepository
from axelcompta.demo_justificatifs import InMemoryJustificatifRepository
from axelcompta.demo_seed import TENANT_DEMO, amorcer_demo
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.agregats import AgregatStocke
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.signature_postgres import PostgresSignatureRepository

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent
_CLE = ec.generate_private_key(ec.SECP256R1())
DOSSIERS = ("DEMO_karim", "DEMO_sophie", "DEMO_yanis")


def _jeton(**metadonnees: dict[str, str]) -> str:
    charge = {
        "sub": "u-1",
        "email": "x@example.com",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **metadonnees,
    }
    return jwt.encode(charge, _CLE, algorithm="ES256")


def _en_tete(**metadonnees: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_jeton(**metadonnees)}"}


GESTIONNAIRE = _en_tete(app_metadata={"tenant_id": "TENANT_DEMO"})


def _chauffeur(dossier_id: str) -> dict[str, str]:
    return _en_tete(app_metadata={"dossier_id": dossier_id})


@pytest.fixture
def engine_web(engine: Engine) -> Iterator[Engine]:
    command.upgrade(_config(), "head")
    url = make_url(str(engine.url)).set(username="axelcompta_web", password="web_password_dev")
    moteur = create_engine(url)
    yield moteur
    moteur.dispose()


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _application(engine_web: Engine, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Une instance de l'API : en construire une seconde sur la même base
    revient à redémarrer le serveur."""
    monkeypatch.setattr(demo_api, "_ENGINE_DEMO", engine_web)
    app = demo_api.create_app()
    comptes, justificatifs = InMemoryCompteRepository(), InMemoryJustificatifRepository()
    app.dependency_overrides[demo_api.get_comptes] = lambda: comptes
    app.dependency_overrides[demo_api.get_justificatifs] = lambda: justificatifs
    return TestClient(app)


@pytest.fixture
def api(engine: Engine, engine_web: Engine, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SUPABASE_URL", "https://exemple.supabase.co")
    monkeypatch.setattr(
        demo_auth,
        "_jwks_client",
        lambda url: SimpleNamespace(
            get_signing_key_from_jwt=lambda jeton: SimpleNamespace(key=_CLE.public_key())
        ),
    )
    amorcer_demo(
        PostgresDossierRepository(engine),
        PostgresLedgerService(engine),
        PostgresPropositionRepository(engine),
    )
    return _application(engine_web, monkeypatch)


# --- référence : le calcul d'avant, lu avec le propriétaire -----------------


def _dossiers(engine: Engine) -> list[Dossier]:
    return list(PostgresDossierRepository(engine).lister_par_tenant(TENANT_DEMO))


def _reference(engine: Engine) -> dict[str, tuple[Any, ...]]:
    base = PostgresLedgerService(engine)
    decisions = PostgresDecisionRepository(engine)
    provisions = PostgresProvisionsClotureRepository(engine)
    comptes = InMemoryCompteRepository()
    signatures = PostgresSignatureRepository(engine)
    attendu: dict[str, tuple[Any, ...]] = {}
    for dossier in _dossiers(engine):
        resume = demo_api._resume(
            dossier,
            demo_api._ledger_avec_decisions(dossier, base, decisions),
            comptes,
            signatures,
            True,
            demo_api._provisions_saisies(dossier, provisions),
        )
        attendu[dossier.id] = (
            resume.ca_ht_cts,
            resume.charges_cts,
            resume.resultat_cts,
            resume.exercice_debut,
            resume.exercice_fin,
            resume.alerte_tva,
        )
    return attendu


def _affiche(client: TestClient) -> dict[str, tuple[Any, ...]]:
    reponse = client.get("/dossiers", headers=GESTIONNAIRE)
    assert reponse.status_code == 200, reponse.text
    return {
        ligne["dossier_id"]: (
            ligne["ca_ht_cts"],
            ligne["charges_cts"],
            ligne["resultat_cts"],
            ligne["exercice_debut"],
            ligne["exercice_fin"],
            ligne["alerte_tva"],
        )
        for ligne in reponse.json()
    }


@pytest.fixture
def calculs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Les dossiers recalculés depuis le dernier `clear()`."""
    calcules: list[str] = []
    calculer = demo_api._calculer_agregat

    def espion(dossier: Dossier, *args: Any) -> AgregatStocke:
        calcules.append(str(dossier.id))
        return calculer(dossier, *args)

    monkeypatch.setattr(demo_api, "_calculer_agregat", espion)
    return calcules


# --- écritures : les routes de l'API, et ce que posent les scripts ----------


def _a_trancher(api: TestClient, dossier_id: str = "DEMO_sophie") -> list[str]:
    lignes = api.get(f"/dossiers/{dossier_id}/transactions", headers=_chauffeur(dossier_id)).json()
    return [ligne["ecriture_id"] for ligne in lignes if ligne["statut"] == "à trancher"]


def _trancher(api: TestClient, engine: Engine, _numero: int) -> str:
    ecriture_id = _a_trancher(api)[0]
    reponse = api.post(
        f"/dossiers/DEMO_sophie/transactions/{ecriture_id}/decision",
        json={"categorie": "usage_personnel"},
        headers=_chauffeur("DEMO_sophie"),
    )
    assert reponse.status_code == 200, reponse.text
    return "DEMO_sophie"


def _imputer(api: TestClient, engine: Engine, _numero: int) -> str:
    ecriture_id = _a_trancher(api)[0]
    reponse = api.post(
        "/expert/imputations",
        json={"dossier_id": "DEMO_sophie", "ecriture_id": ecriture_id, "compte": "6061"},
        headers=GESTIONNAIRE,
    )
    # 204 avant AXE-567, 200 (les sujets du dossier) après : sans importance ici.
    assert reponse.status_code in (200, 204), reponse.text
    return "DEMO_sophie"


def _provisionner(api: TestClient, engine: Engine, numero: int) -> str:
    reponse = api.put(
        "/dossiers/DEMO_yanis/provisions-cloture",
        json={
            "lignes": [
                {
                    "nature": "fnp",
                    "compte_charge": "6061",
                    "centimes": 1000 * (numero + 1),
                    "libelle": f"Estimation {numero}",
                }
            ]
        },
        headers=_chauffeur("DEMO_yanis"),
    )
    assert reponse.status_code == 200, reponse.text
    return "DEMO_yanis"


def _script(
    dossier_id: str, compte_produit: str, sens_banque: Sens
) -> Callable[[TestClient, Engine, int], str]:
    """Une écriture posée hors API, comme la synchro Digifactory : aucune route."""

    def poser(api: TestClient, engine: Engine, numero: int) -> str:
        dossier = next(d for d in _dossiers(engine) if d.id == dossier_id)
        contre = Sens.DEBIT if sens_banque is Sens.CREDIT else Sens.CREDIT
        PostgresLedgerService(engine).enregistrer(
            Ecriture(
                id=EcritureId(f"bt-{dossier_id}-{compte_produit}-{numero}"),
                dossier_id=DossierId(dossier_id),
                journal=Journal.BQ,
                date=dossier.exercice_debut + timedelta(days=5),
                libelle=f"script {numero}",
                reference_piece=None,
                lignes=(
                    LigneEcriture(compte="512", sens=sens_banque, montant=Money(10_000 + numero)),
                    LigneEcriture(
                        compte=compte_produit, sens=contre, montant=Money(10_000 + numero)
                    ),
                ),
            )
        )
        return dossier_id

    return poser


ECRITURES: dict[str, Callable[[TestClient, Engine, int], str]] = {
    "décision du chauffeur": _trancher,
    "imputation de l'expert": _imputer,
    "provision du chauffeur": _provisionner,
    "recette posée par un script": _script("DEMO_karim", "706", Sens.DEBIT),
    "dépense posée par un script": _script("DEMO_karim", "625", Sens.CREDIT),
}


# --- les tests -------------------------------------------------------------


def test_la_liste_affiche_le_calcul_d_avant_puis_le_relit_sans_rien_recalculer(
    api: TestClient, engine: Engine, calculs: list[str]
) -> None:
    assert _affiche(api) == _reference(engine)
    assert sorted(calculs) == sorted(DOSSIERS)

    calculs.clear()
    assert _affiche(api) == _reference(engine)
    assert calculs == []


def test_apres_un_redemarrage_rien_n_est_recalcule(
    api: TestClient,
    engine: Engine,
    engine_web: Engine,
    monkeypatch: pytest.MonkeyPatch,
    calculs: list[str],
) -> None:
    _affiche(api)
    calculs.clear()

    redemarre = _application(engine_web, monkeypatch)

    assert _affiche(redemarre) == _reference(engine)
    assert calculs == []


@pytest.mark.parametrize("nom", list(ECRITURES))
def test_une_ecriture_ne_fait_recalculer_que_son_dossier(
    nom: str, api: TestClient, engine: Engine, calculs: list[str]
) -> None:
    _affiche(api)
    calculs.clear()

    touche = ECRITURES[nom](api, engine, 1)

    assert _affiche(api) == _reference(engine)
    assert calculs == [touche]


def test_la_liste_suit_chaque_etape_d_une_suite_d_ecritures_au_hasard(
    api: TestClient, engine: Engine, calculs: list[str]
) -> None:
    """40 écritures tirées au hasard (graine fixe), la liste tantôt relue
    après chacune, tantôt après plusieurs : elle égale toujours le calcul
    d'avant, et ne recalcule que les dossiers touchés depuis la dernière lecture."""
    hasard = random.Random(566)
    numeros = count(1)
    touches: set[str] = set()
    assert _affiche(api) == _reference(engine)

    for _ in range(40):
        nom = hasard.choice(list(ECRITURES))
        if nom in ("décision du chauffeur", "imputation de l'expert") and len(_a_trancher(api)) < 2:
            nom = "recette posée par un script"
        touches.add(ECRITURES[nom](api, engine, next(numeros)))
        if hasard.random() < 0.6:
            calculs.clear()
            assert _affiche(api) == _reference(engine)
            assert set(calculs) == touches
            assert len(calculs) == len(touches)
            touches.clear()
