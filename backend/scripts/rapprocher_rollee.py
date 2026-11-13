"""Relier les users Rollee existants à leurs dossiers (AXE-911).

Simulation par défaut : lit Rollee (users, profils, IBAN de versement) et
Digifactory, compare par empreintes, et affiche le bilan sans rien écrire.
Rien en clair n'est affiché ni gardé : seulement des nombres.

`--appliquer` pose les liens sûrs et remplit la file « à choisir » du
gestionnaire. À ne lancer qu'après avoir posé le bilan de la simulation sur
le ticket. Le jeton Rollee renouvelé en route est gardé dans le branchement.

Usage, depuis backend/ (DATABASE_URL et AXELCOMPTA_CLE_INTEGRATIONS définis) :

    python scripts/rapprocher_rollee.py --tenant TENANT_ID
    python scripts/rapprocher_rollee.py --tenant TENANT_ID --appliquer
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.rapprochement_rollee_service import depots_postgres, passer_tenant


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument(
        "--appliquer", action="store_true", help="écrire les liens (sinon simulation)"
    )
    arguments = parseur.parse_args()
    depots = depots_postgres(engine_depuis_env())
    lignes = asyncio.run(
        passer_tenant(depots, TenantId(arguments.tenant), arguments.appliquer, datetime.now(UTC))
    )
    for ligne in lignes or ["aucun branchement Rollee actif"]:
        print(ligne)
    return 0


if __name__ == "__main__":
    sys.exit(main())
