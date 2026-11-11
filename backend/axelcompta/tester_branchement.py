"""Bouton « Tester » d'un branchement (AXE-872).

Composition root (doc 18) : chaque fournisseur est testé par le module qui
sait lui parler. Rien n'est envoyé à un chauffeur : le SMTP se connecte et
s'authentifie, Digifactory lit sa liste de catégories. Un fournisseur de SMS
ne se teste pas sans envoyer un SMS : on le dit.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from axelcompta.ingestion.providers.digifactory import DigifactoryHttpClient, DigifactoryProvider
from axelcompta.tenants.branchements import Branchement
from axelcompta.workflow.rappels_envoi import ExpediteurSmtp


@dataclass(frozen=True, slots=True)
class Essai:
    statut: Literal["ok", "echec", "indisponible"]
    message: str


async def _digifactory(branchement: Branchement) -> Essai:
    client = DigifactoryHttpClient.depuis_parametres(branchement.parametres())
    try:
        sante = await DigifactoryProvider(client_reel=client).health()
    finally:
        await client.aclose()
    if sante.ok:
        return Essai("ok", "Digifactory répond, le jeton est accepté.")
    return Essai("echec", f"Digifactory refuse : {sante.message}")


def tester(branchement: Branchement) -> Essai:
    if branchement.fournisseur == "smtp":
        try:
            ExpediteurSmtp(branchement.parametres()).verifier()
        except Exception as exc:  # noqa: BLE001 — l'erreur devient le message affiché
            return Essai("echec", f"Le serveur refuse : {type(exc).__name__} : {exc}"[:200])
        return Essai("ok", "Connexion et identifiants acceptés. Aucun e-mail envoyé.")
    if branchement.fournisseur == "digifactory":
        try:
            return asyncio.run(_digifactory(branchement))
        except Exception as exc:  # noqa: BLE001 — idem
            return Essai("echec", f"{type(exc).__name__} : {exc}"[:200])
    return Essai(
        "indisponible",
        "Ce fournisseur ne se teste qu'en envoyant un message : il le sera au premier rappel.",
    )
