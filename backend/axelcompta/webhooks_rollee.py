"""Configure les webhooks Rollee d'un branchement (AXE-820).

À lancer une fois par branchement Rollee, **quand l'API est en ligne à une
adresse publique** (Rollee doit pouvoir l'appeler) :

    python -m axelcompta.webhooks_rollee --branchement <id> --url-api https://api.exemple.fr

1. Génère un secret de signature s'il n'y en a pas, et le garde (chiffré)
   dans le branchement.
2. Déclare chez Rollee, pour les types `accounts` et `multi_endpoints`,
   l'adresse `<url-api>/webhooks/rollee/<id>` avec ce secret.

Sans webhook, rien ne casse : la tâche quotidienne relit chaque dossier relié.
Composition root comme `synchro_digifactory.py` (rôle propriétaire).
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime

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


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--branchement", required=True)
    parseur.add_argument("--url-api", required=True)
    args = parseur.parse_args()

    engine = engine_depuis_env()
    depot = PostgresBranchements(engine)
    branchement = branchement_par_id(engine, args.branchement)
    if branchement is None or branchement.type != "rollee":
        print(f"Branchement Rollee inconnu : {args.branchement}", file=sys.stderr)
        return 1
    branchement, secret = assurer_secret(depot, branchement)
    garder = garder_parametre(depot, branchement, "jeton", "webhooks_rollee")
    client = RolleeHttpClient.depuis_parametres(branchement.parametres(), garder)
    url = adresse(args.url_api, branchement.id)
    asyncio.run(configurer(client, url, secret))
    print(f"Webhooks Rollee configurés ({', '.join(TYPES_WEBHOOK)}) vers {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
