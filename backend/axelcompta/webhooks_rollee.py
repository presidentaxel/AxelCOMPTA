"""Prépare le webhook Rollee d'un compte (AXE-820).

Le popup « Relier » montre l'adresse et le secret à reporter dans le
formulaire Rollee. Le secret est chiffré dans le compte. La commande
ci-dessous déclare en plus le webhook chez Rollee, si le compte a une
adresse publique (`url_webhook`) :

    python -m axelcompta.webhooks_rollee --branchement <id>

Sans webhook, rien ne casse : la tâche quotidienne relit chaque dossier relié.
Composition root comme `synchro_digifactory.py` (rôle propriétaire).
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from axelcompta.core.db import engine_depuis_env
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementsRepository,
    Modification,
    garder_parametre,
    modifier,
)
from axelcompta.tenants.branchements_postgres import PostgresBranchements, branchement_par_id

TYPES_WEBHOOK = ("accounts", "multi_endpoints")


def adresse(url_api: str, branchement_id: str) -> str:
    return f"{url_api.rstrip('/')}/webhooks/rollee/{branchement_id}"


def assurer_secret(
    depot: BranchementsRepository, branchement: Branchement
) -> tuple[Branchement, str]:
    """Le secret existant, sinon un nouveau, gardé dans le branchement."""
    parametres = branchement.parametres()
    if parametres.get("secret_webhook"):
        return branchement, parametres["secret_webhook"]
    secret = secrets.token_hex(32)
    a_enregistrer = modifier(
        depot.lister(branchement.tenant_id),
        branchement.id,
        Modification(parametres={**parametres, "secret_webhook": secret}),
    )
    depot.enregistrer(a_enregistrer, "webhooks_rollee", datetime.now(UTC))
    return a_enregistrer[-1], secret


async def configurer(client: RolleeHttpClient, url: str, secret: str) -> None:
    try:
        for type_ in TYPES_WEBHOOK:
            await client.configurer_webhook(type_, url, secret)
    finally:
        await client.aclose()


# Cases du formulaire Rollee (capture du tableau de bord). « Users » ne
# correspond à aucun événement que l'on traite : on ne le fait pas cocher.
EVENEMENTS_A_REPORTER = ("Endpoints", "Multi Endpoints", "Rollee Connect Events")
_HOTES_LOCAUX = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True, slots=True)
class FicheWebhook:
    """Ce que le gestionnaire reporte dans le formulaire Rollee."""

    url: str
    secret: str
    methode: str
    evenements: tuple[str, ...]
    joignable: bool


def preparer(depot: BranchementsRepository, branchement: Branchement, url_api: str) -> FicheWebhook:
    """Crée le secret s'il manque (chiffré dans le compte) et l'adresse de ce compte."""
    branchement, secret = assurer_secret(depot, branchement)
    base = url_api.strip().rstrip("/")
    hote = (urlparse(base).hostname or "").lower()
    return FicheWebhook(
        url=adresse(base, branchement.id),
        secret=secret,
        methode="POST",
        evenements=EVENEMENTS_A_REPORTER,
        joignable=hote not in _HOTES_LOCAUX and hote != "",
    )


@dataclass(frozen=True, slots=True)
class Declaration:
    ok: bool
    message: str


def _url_du_compte(branchement: Branchement) -> str | None:
    """L'adresse publique saisie sur ce compte. Vide si elle n'est pas une URL."""
    url = branchement.parametres().get("url_webhook", "").strip().rstrip("/")
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return None


def declarer(depot: BranchementsRepository, branchement: Branchement, par: str) -> Declaration:
    """Déclare chez Rollee le webhook de ce compte, vers son adresse à lui."""
    if branchement.type != "rollee":
        return Declaration(False, "Ce compte n'est pas un accès Rollee.")
    url = _url_du_compte(branchement)
    if url is None:
        return Declaration(
            False,
            "Indiquez l'adresse publique de l'API de ce compte, dans ses identifiants.",
        )
    branchement, secret = assurer_secret(depot, branchement)
    cible = adresse(url, branchement.id)
    garder = garder_parametre(depot, branchement, "jeton", par)
    client = RolleeHttpClient.depuis_parametres(branchement.parametres(), garder)
    try:
        asyncio.run(configurer(client, cible, secret))
    except Exception as exc:  # noqa: BLE001 — le message revient à l'écran
        return Declaration(False, f"Rollee refuse : {type(exc).__name__} : {exc}"[:200])
    return Declaration(True, f"Webhook déclaré pour ce compte : {cible}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--branchement", required=True)
    args = parseur.parse_args()

    engine = engine_depuis_env()
    depot = PostgresBranchements(engine)
    branchement = branchement_par_id(engine, args.branchement)
    if branchement is None or branchement.type != "rollee":
        print(f"Branchement Rollee inconnu : {args.branchement}", file=sys.stderr)
        return 1
    resultat = declarer(depot, branchement, "webhooks_rollee")
    print(resultat.message, file=sys.stdout if resultat.ok else sys.stderr)
    return 0 if resultat.ok else 1


if __name__ == "__main__":
    sys.exit(main())
