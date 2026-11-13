"""AXE-825 : le gestionnaire voit si la catégorisation est dégradée."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import FastAPI

from axelcompta.api.routes import get_etat_categorisation, get_lots_llm
from axelcompta.categorize.modele_requis import MESSAGE_ABSENT, EtatCategorisation
from axelcompta.workflow.lots_llm import LotsLlmMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)


def test_le_gestionnaire_voit_la_categorisation_degradee() -> None:
    client = _client()
    etat = EtatCategorisation(False, "tfidf_logreg_v2.joblib", MESSAGE_ABSENT)
    cast(FastAPI, client.app).dependency_overrides[get_etat_categorisation] = lambda: etat

    reponse = client.get("/portefeuille/categorisation", headers=_en_tete_gestionnaire())

    assert reponse.status_code == 200
    assert reponse.json() == {"modele_charge": False, "raison": MESSAGE_ABSENT, "llm": None}


def test_un_chauffeur_ne_lit_pas_l_etat_du_portefeuille() -> None:
    client = _client()
    etat = EtatCategorisation(True, "tfidf_logreg_v2.joblib")
    cast(FastAPI, client.app).dependency_overrides[get_etat_categorisation] = lambda: etat
    reponse = client.get("/portefeuille/categorisation", headers=_en_tete("DEMO_karim"))
    assert reponse.status_code == 403


def test_la_ligne_du_llm_compte_les_libelles_sans_le_cout(monkeypatch: pytest.MonkeyPatch) -> None:
    """AXE-887 : Intégrations dit le volume, jamais la dépense."""
    from axelcompta.core.ids import TenantId
    from tests.workflow.test_budget_llm import lot

    monkeypatch.setenv("AXELCOMPTA_LLM_ACTIF", "1")
    client = _client()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_etat_categorisation] = lambda: EtatCategorisation(True, "m")
    lots = LotsLlmMemoire()
    maintenant = datetime.now(UTC)
    lots.enregistrer(
        [
            lot(
                "a",
                tenant_id=TenantId("TENANT_DEMO"),
                cles=("carburant", "peage"),
                cout_usd=100.0,
                soumis_le=maintenant,
            )
        ]
    )
    app.dependency_overrides[get_lots_llm] = lambda: lots
    reponse = client.get("/portefeuille/categorisation", headers=_en_tete_gestionnaire())
    assert reponse.json()["llm"] == {"libelles": 2}
