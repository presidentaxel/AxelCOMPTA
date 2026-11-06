"""Porte les écritures passées au 512 sur le sous-compte de leur compte
bancaire (AXE-832), par des écritures de reclassement (journal OD).

Simulation par défaut : affiche ce qui serait écrit. `--appliquer` écrit.
Rejouable sans doublon. Voir `axelcompta.workflow.ventilation_bancaire`.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/ventiler_comptes_bancaires.py --dossier DIGI_22755
    python scripts/ventiler_comptes_bancaires.py --tenant TENANT_DEMO --appliquer
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_bancaires_postgres import PostgresCompteBancaireRepository
from axelcompta.ingestion.journal_postgres import PostgresJournalIngestion
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.synchro_digifactory import SOURCE
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.ventilation_bancaire import ventilation_du_dossier


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
    journal = PostgresJournalIngestion(engine)
    comptes = PostgresCompteBancaireRepository(engine)
    for dossier in _dossiers(PostgresDossierRepository(engine), arguments):
        reclassements = ventilation_du_dossier(
            dossier.id, ledger.grand_livre(dossier.id), journal, comptes, SOURCE
        )
        par_compte = Counter(r.lignes[0].compte for r in reclassements)
        detail = ", ".join(f"{compte} : {n}" for compte, n in sorted(par_compte.items()))
        print(f"{dossier.id} : {len(reclassements)} reclassement(s) {detail}".rstrip(), flush=True)
        if arguments.appliquer:
            for reclassement in reclassements:
                ledger.enregistrer(reclassement)
    if not arguments.appliquer:
        print("Simulation : rien n'a été écrit. Relancer avec --appliquer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
