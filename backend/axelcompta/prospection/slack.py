"""Prévenir l'équipe sur Slack d'une demande d'échange (AXE-949).

Un webhook entrant : une adresse secrète qui ne sert qu'à poster dans un
canal. Elle vient de l'environnement (`AXELCOMPTA_SLACK_DEMANDES_WEBHOOK`),
jamais du code, et n'est jamais écrite dans un journal ni dans la base.
Sans elle, la demande est gardée et l'équipe n'est pas prévenue.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from axelcompta.prospection.models import DemandeEchange

VARIABLE_WEBHOOK = "AXELCOMPTA_SLACK_DEMANDES_WEBHOOK"
# Un webhook Slack commence toujours ainsi : toute autre adresse est refusée,
# pour qu'une variable mal remplie n'envoie pas les demandes ailleurs.
PREFIXE_WEBHOOK = "https://hooks.slack.com/"
DELAI_S = 5.0
LONGUEUR_MESSAGE_SLACK = 1000
ROLES_LIBELLES = {"cabinet": "un cabinet", "centrale": "une centrale"}


class Notifieur(Protocol):
    def notifier(self, demande: DemandeEchange) -> None:
        """Lève une exception si Slack refuse ou ne répond pas."""
        ...


def webhook_depuis_env(environ: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if environ is None else environ
    adresse = source.get(VARIABLE_WEBHOOK, "").strip()
    return adresse if adresse.startswith(PREFIXE_WEBHOOK) else None


def _echapper(texte: str) -> str:
    """Slack lit `&`, `<` et `>` : sans ça, un message pourrait mentionner tout le canal."""
    return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def message_slack(demande: DemandeEchange) -> dict[str, Any]:
    lignes = [
        "*Nouvelle demande d'échange AxeLCompta*",
        f"Nom : {_echapper(demande.nom)}",
        f"E-mail : {_echapper(demande.email)}",
        f"Organisation : {_echapper(demande.organisation)}",
        f"Profil : {ROLES_LIBELLES[demande.role]}",
    ]
    if demande.message:
        court = demande.message[:LONGUEUR_MESSAGE_SLACK]
        suite = "…" if len(demande.message) > LONGUEUR_MESSAGE_SLACK else ""
        lignes.append(f"Message : {_echapper(court)}{suite}")
    return {"text": "\n".join(lignes)}


class NotifieurSlack:
    def __init__(self, webhook: str, client: httpx.Client | None = None) -> None:
        self._webhook = webhook
        self._client = client

    def notifier(self, demande: DemandeEchange) -> None:
        corps = message_slack(demande)
        if self._client is not None:
            self._client.post(self._webhook, json=corps, timeout=DELAI_S).raise_for_status()
            return
        with httpx.Client() as client:
            client.post(self._webhook, json=corps, timeout=DELAI_S).raise_for_status()


def notifieur_depuis_env() -> Notifieur | None:
    adresse = webhook_depuis_env()
    return NotifieurSlack(adresse) if adresse is not None else None
