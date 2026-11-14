"""Relire les comptes flotte de la carte qui n'ont pas encore de nom.

Simulation par défaut : un nombre, rien n'est écrit. `--appliquer` relit les
profils (3 appels à la fois au plus) et remet la fiche à jour. Aucun nom
n'est affiché.

Usage, depuis backend/ :

    python scripts/relire_carte_rollee.py --tenant TENANT_ID
    python scripts/relire_carte_rollee.py --tenant TENANT_ID --appliquer
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.ingestion.cartes_rollee import sans_nom
from axelcompta.ingestion.providers.rollee import RolleeIndisponible
from axelcompta.ingestion.rapprochement_rollee import UserRollee
from axelcompta.plateformes_rollee import client_du_branchement
from axelcompta.rapprochement_rollee_service import (
    APPELS_SIMULTANES,
    DepotsRapprochement,
    cle_empreintes,
    depots_postgres,
    lire_user,
)
from axelcompta.tenants.branchements import Branchement


def main() -> int:
    arguments = _arguments()
    return asyncio.run(_relire(arguments.tenant, arguments.appliquer))


async def _relire(tenant_id: str, appliquer: bool) -> int:
    depots = depots_postgres(engine_depuis_env())
    tenant = TenantId(tenant_id)
    cibles = [
        (branchement, user)
        for branchement, user in depots.cartes.du_portefeuille(tenant)
        if sans_nom(user)
    ]
    print(f"{len(cibles)} comptes à relire.")
    if appliquer and cibles:
        await _appliquer(depots, tenant, cibles)
    return 0


async def _appliquer(
    depots: DepotsRapprochement, tenant: TenantId, cibles: list[tuple[str, UserRollee]]
) -> None:
    limite = asyncio.Semaphore(APPELS_SIMULTANES)
    cle = cle_empreintes()
    connus = {b.id: b for b in depots.services.branchements.lister(tenant)}
    maintenant = datetime.now(UTC)
    resultats = await asyncio.gather(
        *(
            _un(depots, tenant, branchement_id, user, connus, cle, limite, maintenant)
            for branchement_id, user in cibles
        )
    )
    avec_nom = sum(1 for ok in resultats if ok)
    print(f"{avec_nom} fiches avec un nom, {len(resultats) - avec_nom} encore sans.")


async def _un(
    depots: DepotsRapprochement,
    tenant: TenantId,
    branchement_id: str,
    user: UserRollee,
    connus: dict[str, Branchement],
    cle: bytes,
    limite: asyncio.Semaphore,
    maintenant: datetime,
) -> bool:
    branchement = connus.get(branchement_id)
    if branchement is None:
        return False
    client = client_du_branchement(depots.services, branchement)
    try:
        lu = await lire_user(
            client,
            {"id": user.user_id, "accounts_number": user.accounts_number},
            cle,
            limite,
        )
    except RolleeIndisponible:
        return False
    finally:
        await client.aclose()
    depots.cartes.garder(tenant, branchement_id, lu, maintenant)
    return bool(lu.empreintes.noms)


def _arguments() -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument("--appliquer", action="store_true")
    return parseur.parse_args()


if __name__ == "__main__":
    sys.exit(main())
