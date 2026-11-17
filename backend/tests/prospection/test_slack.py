"""AXE-949 : le webhook Slack est un secret, et le message ne mentionne personne."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from axelcompta.prospection.models import DemandeEchange
from axelcompta.prospection.slack import (
    LONGUEUR_MESSAGE_SLACK,
    NotifieurSlack,
    message_slack,
    notifieur_depuis_env,
    webhook_depuis_env,
)

WEBHOOK = "https://hooks.slack.com/services/T000/B000/secret-xyz"
VARIABLE = "AXELCOMPTA_SLACK_DEMANDES_WEBHOOK"


def _demande(role: str = "cabinet", message: str | None = None) -> DemandeEchange:
    return DemandeEchange(
        id="d1",
        nom="Claire Martin",
        email="claire@cabinet-martin.fr",
        organisation="Cabinet Martin",
        role="centrale" if role == "centrale" else "cabinet",
        message=message,
        cree_le=datetime(2026, 11, 16, 14, 0, tzinfo=UTC),
    )


def test_seule_une_adresse_slack_est_acceptee() -> None:
    assert webhook_depuis_env({VARIABLE: f" {WEBHOOK} "}) == WEBHOOK
    assert webhook_depuis_env({VARIABLE: "https://exemple.fr/hook"}) is None
    assert webhook_depuis_env({VARIABLE: "http://hooks.slack.com/x"}) is None
    assert webhook_depuis_env({}) is None


def test_sans_webhook_il_n_y_a_pas_de_notifieur(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    assert notifieur_depuis_env() is None
    monkeypatch.setenv(VARIABLE, WEBHOOK)
    assert isinstance(notifieur_depuis_env(), NotifieurSlack)


def test_le_message_reprend_la_demande() -> None:
    texte = message_slack(_demande(message="Nous suivons 40 dossiers."))["text"]
    assert "Claire Martin" in texte
    assert "claire@cabinet-martin.fr" in texte
    assert "Cabinet Martin" in texte
    assert "un cabinet" in texte
    assert "Nous suivons 40 dossiers." in texte


def test_une_centrale_est_dite_comme_telle() -> None:
    assert "une centrale" in message_slack(_demande(role="centrale"))["text"]


def test_le_message_ne_peut_mentionner_personne() -> None:
    texte = message_slack(_demande(message="<!channel> <@U123> a & b"))["text"]
    assert "<!channel>" not in texte
    assert "<@U123>" not in texte
    assert "&lt;!channel&gt;" in texte
    assert "a &amp; b" in texte


def test_un_long_message_est_coupe() -> None:
    texte = message_slack(_demande(message="x" * (LONGUEUR_MESSAGE_SLACK + 50)))["text"]
    assert "x" * LONGUEUR_MESSAGE_SLACK in texte
    assert "x" * (LONGUEUR_MESSAGE_SLACK + 1) not in texte
    assert texte.endswith("…")


def _client(reponse: httpx.Response, appels: list[httpx.Request]) -> httpx.Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        appels.append(requete)
        return reponse

    return httpx.Client(transport=httpx.MockTransport(repondre))


def test_le_notifieur_poste_le_message_sur_le_webhook() -> None:
    appels: list[httpx.Request] = []
    client = _client(httpx.Response(200, text="ok"), appels)
    NotifieurSlack(WEBHOOK, client).notifier(_demande())
    assert [str(a.url) for a in appels] == [WEBHOOK]
    assert b"Claire Martin" in appels[0].content


def test_un_refus_de_slack_leve_une_erreur() -> None:
    appels: list[httpx.Request] = []
    client = _client(httpx.Response(404, text="no_service"), appels)
    with pytest.raises(httpx.HTTPStatusError):
        NotifieurSlack(WEBHOOK, client).notifier(_demande())
