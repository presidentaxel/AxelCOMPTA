"""Amorçage de la démo puis API **sans aucune dépendance surchargée pour
Postgres** : le chemin réel de bout en bout (seed -> Postgres -> routes),
seuls Supabase (comptes) et le stockage de justificatifs restent stubés."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

import axelcompta.api.auth as demo_auth
import axelcompta.api.routes as demo_api
from axelcompta.comptes_memoire import InMemoryCompteRepository
from axelcompta.core.db import metadata
from axelcompta.demo_seed import AmorcageIncompletError, amorcer_demo
from axelcompta.documents.justificatifs import InMemoryJustificatifRepository
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository

pytestmark = pytest.mark.integration

_CLE = ec.generate_private_key(ec.SECP256R1())


def _jeton(**metadonnees: dict[str, str]) -> str:
    charge = {
        "sub": "u-1",
        "email": "x@example.com",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "aal": "aal2",  # code TOTP vérifié : l'admin l'exige (AXE-812)
        **metadonnees,
    }
    return jwt.encode(charge, _CLE, algorithm="ES256")


@pytest.fixture
def client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    metadata.create_all(engine)
    monkeypatch.setattr(demo_api, "_ENGINE_DEMO", engine)
    monkeypatch.setenv("SUPABASE_URL", "https://exemple.supabase.co")
    monkeypatch.setattr(
        demo_auth,
        "_jwks_client",
        lambda url: SimpleNamespace(
            get_signing_key_from_jwt=lambda jeton: SimpleNamespace(key=_CLE.public_key())
        ),
    )
    app = demo_api.create_app()
    comptes, justificatifs = InMemoryCompteRepository(), InMemoryJustificatifRepository()
    app.dependency_overrides[demo_api.get_comptes] = lambda: comptes
    app.dependency_overrides[demo_api.get_justificatifs] = lambda: justificatifs
    return TestClient(app)


def _amorcer(engine: Engine) -> list[str]:
    return amorcer_demo(
        PostgresDossierRepository(engine),
        PostgresLedgerService(engine),
        PostgresPropositionRepository(engine),
    )


def test_amorcage_est_idempotent(engine: Engine) -> None:
    metadata.create_all(engine)
    assert _amorcer(engine) == ["DEMO_karim", "DEMO_sophie", "DEMO_yanis"]
    assert _amorcer(engine) == []


def test_amorcage_interrompu_est_refuse_plutot_que_complete(engine: Engine) -> None:
    from sqlalchemy import text

    metadata.create_all(engine)
    _amorcer(engine)
    with engine.begin() as connexion:
        connexion.execute(
            text(
                "DELETE FROM lignes_ecriture WHERE ecriture_id = "
                "(SELECT id FROM ecritures WHERE dossier_id = 'DEMO_karim' LIMIT 1)"
            )
        )
        connexion.execute(
            text(
                "DELETE FROM ecritures WHERE id = "
                "(SELECT id FROM ecritures WHERE dossier_id = 'DEMO_karim' LIMIT 1)"
            )
        )

    with pytest.raises(AmorcageIncompletError):
        _amorcer(engine)


def test_gestionnaire_voit_le_portefeuille_depuis_postgres(
    engine: Engine, client: TestClient
) -> None:
    _amorcer(engine)
    en_tete = {"Authorization": f"Bearer {_jeton(app_metadata={'tenant_id': 'TENANT_DEMO'})}"}

    reponse = client.get("/dossiers", headers=en_tete)

    assert reponse.status_code == 200
    assert {d["dossier_id"] for d in reponse.json()} == {
        "DEMO_karim",
        "DEMO_sophie",
        "DEMO_yanis",
    }


def test_chauffeur_tranche_puis_la_decision_survit_en_base(
    engine: Engine, client: TestClient
) -> None:
    """Le cas Sophie de bout en bout sur Postgres : transaction à trancher,
    décision, proposition d'origine relue depuis la base, écriture 455."""
    _amorcer(engine)
    en_tete = {"Authorization": f"Bearer {_jeton(app_metadata={'dossier_id': 'DEMO_sophie'})}"}
    transactions = client.get("/dossiers/DEMO_sophie/transactions", headers=en_tete).json()
    a_trancher = next(t for t in transactions if t["statut"] == "à trancher")

    reponse = client.post(
        f"/dossiers/DEMO_sophie/transactions/{a_trancher['ecriture_id']}/decision",
        json={"categorie": "usage_personnel"},
        headers=en_tete,
    )

    assert reponse.status_code == 200
    assert reponse.json()["compte"] == "455"
    relues = client.get("/dossiers/DEMO_sophie/transactions", headers=en_tete).json()
    assert next(t for t in relues if t["ecriture_id"] == a_trancher["ecriture_id"])["statut"] == (
        "validé"
    )
