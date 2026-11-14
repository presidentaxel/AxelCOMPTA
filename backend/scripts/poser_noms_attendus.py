"""Poser les noms attendus sur les liens Rollee d'avant la PR 170 (AXE-922).

Simulation par défaut : pour chaque lien posé par le rapprochement ou à la
main sans noms attendus, dit combien de comptes de plateforme seraient
retenus, et combien sont au nom d'un autre chauffeur. Rien n'est écrit.
`--appliquer` pose les noms et relit les comptes. Ne lit aucun revenu.
Aucun nom n'est affiché.

À lancer avant toute synchro Rollee après la migration f3a9c7e15d82 :

    python scripts/poser_noms_attendus.py --tenant TENANT_ID
    python scripts/poser_noms_attendus.py --tenant TENANT_ID --appliquer
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.noms_attendus_rollee import poser_noms_attendus
from axelcompta.rapprochement_rollee_service import depots_postgres


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument("--appliquer", action="store_true", help="écrire (sinon simulation)")
    arguments = parseur.parse_args()
    depots = depots_postgres(engine_depuis_env())
    lignes = asyncio.run(
        poser_noms_attendus(depots, TenantId(arguments.tenant), arguments.appliquer)
    )
    for texte in lignes:
        print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
