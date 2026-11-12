"""Bouton « Tester » d'un branchement (AXE-872).

Composition root (doc 18) : chaque fournisseur est testé par le module qui
sait lui parler. Rien n'est envoyé à un chauffeur : le SMTP se connecte et
s'authentifie, Digifactory lit sa liste de catégories, Rollee renouvelle son
jeton (le nouveau est gardé par `sur_nouveau_jeton`). Un fournisseur de SMS
ne se teste pas sans envoyer un SMS : on le dit.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from axelcompta.ingestion.providers.digifactory import DigifactoryHttpClient, DigifactoryProvider
from axelcompta.ingestion.providers.rollee import RolleeHttpClient, RolleeProvider
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


async def _rollee(
    branchement: Branchement, sur_nouveau_jeton: Callable[[str], None] | None
) -> Essai:
    client = RolleeHttpClient.depuis_parametres(branchement.parametres(), sur_nouveau_jeton)
    try:
        sante = await RolleeProvider(client=client, comptes_du_dossier=lambda _d: ()).health()
    finally:
        await client.aclose()
    if sante.ok:
        return Essai("ok", f"Rollee répond, le jeton est accepté ({client.environnement}).")
    return Essai("echec", f"Rollee refuse : {sante.message}"[:200])


def tester(
    branchement: Branchement, sur_nouveau_jeton: Callable[[str], None] | None = None
) -> Essai:
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
    if branchement.fournisseur == "rollee":
        try:
            return asyncio.run(_rollee(branchement, sur_nouveau_jeton))
        except Exception as exc:  # noqa: BLE001 — idem
            return Essai("echec", f"{type(exc).__name__} : {exc}"[:200])
    return Essai(
        "indisponible",
        "Ce fournisseur ne se teste qu'en envoyant un message : il le sera au premier rappel.",
    )
