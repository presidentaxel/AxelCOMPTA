"""Écrit au grand livre les décisions humaines prises avant AXE-420.

Avant AXE-420, une décision du chauffeur n'écrivait rien : elle était
réappliquée à chaque lecture. Ce script rejoue, pour chaque opération qui
n'a encore aucun reclassement, ses décisions dans l'ordre, et écrit les OD
de reclassement correspondantes (`axelcompta.workflow.reclassement`).

Simulation par défaut : affiche ce qui serait écrit. `--appliquer` écrit.
Rejouable sans doublon. À lancer juste après le déploiement d'AXE-420 :
d'ici là, les écrans appliquent encore ces décisions par-dessus, donc rien
ne change à l'écran, avant comme après.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/materialiser_decisions.py --tenant TENANT_DEMO
    python scripts/materialiser_decisions.py --tenant TENANT_DEMO --appliquer
"""

from __future__ import annotations

import argparse
import sys

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.statuts import configuration_de
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.reclassement import reclassements_a_reprendre


def _dossiers(
    depot: PostgresDossierRepository, arguments: argparse.Namespace
) -> tuple[Dossier, ...]:
    if arguments.dossier:
        dossier = depot.obtenir(DossierId(arguments.dossier))
        if dossier is None:
            raise SystemExit(f"dossier inconnu : {arguments.dossier}")
        return (dossier,)
    return depot.lister_par_tenant(TenantId(arguments.tenant))


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cible = parseur.add_mutually_exclusive_group(required=True)
    cible.add_argument("--dossier")
    cible.add_argument("--tenant")
    parseur.add_argument("--appliquer", action="store_true", help="écrire (sinon simulation)")
    arguments = parseur.parse_args()

    engine = engine_depuis_env()
    ledger = PostgresLedgerService(engine)
    decisions = PostgresDecisionRepository(engine)
    comptes_pack = charger_compte_par_categorie()
    total = 0
    for dossier in _dossiers(PostgresDossierRepository(engine), arguments):
        a_ecrire = reclassements_a_reprendre(
            ledger.grand_livre(dossier.id),
            decisions.lister_decisions(dossier.id),
            (configuration_de(dossier).comptes_categories_statut(), comptes_pack),
            ledger.periodes_closes(dossier.id),
        )
        total += len(a_ecrire)
        print(f"{dossier.id} : {len(a_ecrire)} reclassement(s)", flush=True)
        if arguments.appliquer:
            for reclassement in a_ecrire:
                ledger.enregistrer(reclassement)
    mode = "écrits" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} reclassement(s) {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
