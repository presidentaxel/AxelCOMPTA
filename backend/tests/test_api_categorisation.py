"""AXE-825 : le gestionnaire voit si la catégorisation est dégradée."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from axelcompta.api.routes import get_etat_categorisation
from axelcompta.categorize.modele_requis import MESSAGE_ABSENT, EtatCategorisation
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
    assert reponse.json() == {"modele_charge": False, "raison": MESSAGE_ABSENT}


def test_un_chauffeur_ne_lit_pas_l_etat_du_portefeuille() -> None:
    client = _client()
    etat = EtatCategorisation(True, "tfidf_logreg_v2.joblib")
    cast(FastAPI, client.app).dependency_overrides[get_etat_categorisation] = lambda: etat
    reponse = client.get("/portefeuille/categorisation", headers=_en_tete("DEMO_karim"))
    assert reponse.status_code == 403
