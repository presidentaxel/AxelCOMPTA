from __future__ import annotations

import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.observabilite import brancher, installer_sentry
from axelcompta.core.journal_json import ecrire
from axelcompta.core.metriques import Registre


def test_le_registre_rend_le_texte_prometheus() -> None:
    registre = Registre()
    registre.incrementer("ledger_balance_error")
    registre.jauger("categorization_rate_rule", 0.62)
    texte = registre.texte()
    assert "ledger_balance_error 1" in texte
    assert "categorization_rate_rule 0.62" in texte


def test_sentry_reste_eteint_sans_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert installer_sentry() is False
    assert installer_sentry("") is False


def test_le_journal_est_une_ligne_json() -> None:
    sortie = io.StringIO()
    ecrire("info", "ledger", "balance.ok", sortie=sortie, tenant_id="ten_1")
    ligne = json.loads(sortie.getvalue())
    assert ligne["level"] == "info"
    assert ligne["module"] == "ledger"
    assert ligne["event"] == "balance.ok"
    assert ligne["tenant_id"] == "ten_1"
    assert "timestamp" in ligne


def test_la_route_metrics_compte_la_requete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    app = FastAPI()
    brancher(app)
    client = TestClient(app)
    client.get("/metrics")
    reponse = client.get("/metrics")
    assert reponse.status_code == 200
    assert 'http_request_count{method="GET",status="200"}' in reponse.text
