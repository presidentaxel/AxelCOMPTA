"""Reprend la TVA déductible des dépenses imputées TTC avant AXE-831.

Pour chaque opération déjà imputée (par la synchro ou par une décision), écrit
l'OD qui sépare la TVA récupérable estimée (`workflow.reprise_tva`). Rien n'est
modifié ni supprimé : tout passe par de nouvelles OD.

Simulation par défaut : affiche ce qui serait écrit. `--appliquer` écrit.
Rejouable sans doublon. Les dossiers en franchise de TVA ne bougent pas.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/reprendre_tva_deductible.py --dossier DOSSIER_ID
    python scripts/reprendre_tva_deductible.py --tenant TENANT --appliquer
"""

from __future__ import annotations

import argparse
import sys

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.statuts import configuration_de
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.reprise_tva import reprises_tva


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
    propositions = PostgresPropositionRepository(engine)
    comptes_pack = charger_compte_par_categorie()
    total = 0
    for dossier in _dossiers(PostgresDossierRepository(engine), arguments):
        categories: dict[EcritureId, str] = {
            ecriture_id: p.categorie for ecriture_id, p in propositions.lister(dossier.id).items()
        }
        for decision in sorted(decisions.lister_decisions(dossier.id), key=lambda d: d.decide_le):
            categories[decision.ecriture_id] = decision.categorie
        a_ecrire = reprises_tva(
            ledger.grand_livre(dossier.id),
            categories,
            (configuration_de(dossier).comptes_categories_statut(), comptes_pack),
            dossier.regime_tva,
            ledger.periodes_closes(dossier.id),
        )
        total += len(a_ecrire)
        print(f"{dossier.id} : {len(a_ecrire)} OD de TVA", flush=True)
        if arguments.appliquer:
            for od in a_ecrire:
                ledger.enregistrer(od)
    mode = "écrites" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} OD {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
