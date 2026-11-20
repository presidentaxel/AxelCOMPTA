"""Repasse dans le pipeline les opérations restées au 471 (AXE-850).

Même règle qu'une synchro neuve : au-dessus du seuil, l'OD de reclassement
d'AXE-420 (le 512 ne bouge pas) ; en dessous, l'opération reste à trancher.
Ni une décision humaine, ni un reclassement, ni une opération annulée,
soldée par une semaine Rollee ou en virement interne ne sont touchés. Les
dossiers exclus par un tag (sociétés du gestionnaire) sont sautés.

Simulation par défaut : par dossier, les opérations au 471, celles qui
seraient reclassées et vers quels comptes. `--appliquer` écrit. Rejouable.

Usage, depuis backend/ (DATABASE_URL défini, modèle disponible) :

    python scripts/reprendre_attente.py --dossier DIGI_22755
    python scripts/reprendre_attente.py --tenant TENANT_DEMO --appliquer
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from axelcompta.categorize.ml_fallback import charger_calibration
from axelcompta.categorize.modele_requis import modele_pour_synchro
from axelcompta.categorize.rules_and_ml import RulesAndMlPipeline
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_regles,
)
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.statuts import configuration_de
from axelcompta.tenants.tags import etat_du_portefeuille
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.reprise_attente import reprendre
from axelcompta.workflow.revue import COMPTE_ATTENTE


def _dossiers(
    depot: PostgresDossierRepository, arguments: argparse.Namespace
) -> tuple[Dossier, ...]:
    if arguments.dossier:
        dossier = depot.obtenir(DossierId(arguments.dossier))
        if dossier is None:
            raise SystemExit(f"dossier inconnu : {arguments.dossier}")
        return (dossier,)
    return depot.lister_par_tenant(TenantId(arguments.tenant))


def _vers(ods: tuple[Ecriture, ...]) -> str:
    """« 6061 : 42 ; 625 : 7 » : le compte qui reçoit chaque reclassement."""
    comptes = Counter(
        next(lg.compte for lg in od.lignes if not lg.compte.startswith(COMPTE_ATTENTE))
        for od in ods
    )
    return " ; ".join(f"{c} : {n}" for c, n in comptes.most_common())


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cible = parseur.add_mutually_exclusive_group(required=True)
    cible.add_argument("--dossier")
    cible.add_argument("--tenant")
    parseur.add_argument("--appliquer", action="store_true", help="écrire (sinon simulation)")
    arguments = parseur.parse_args()

    engine = engine_depuis_env()
    modele = modele_pour_synchro()
    pipeline = RulesAndMlPipeline(
        regles=charger_regles(),
        modele=modele,
        calibration=charger_calibration() if modele is not None else None,
        categories_banque=charger_categories_banque(),
    )
    ledger = PostgresLedgerService(engine)
    decisions = PostgresDecisionRepository(engine)
    propositions = PostgresPropositionRepository(engine)
    comptes_pack = charger_compte_par_categorie()
    dossiers = _dossiers(PostgresDossierRepository(engine), arguments)
    etat = (
        etat_du_portefeuille(PostgresTagsRepository(engine), dossiers[0].tenant_id)
        if dossiers
        else None
    )
    total = 0
    for dossier in dossiers:
        if etat is not None and etat.exclu(dossier.id, "categorisation"):
            print(f"{dossier.id} : exclu par un tag, sauté", flush=True)
            continue
        ecritures = ledger.grand_livre(dossier.id)
        decidees = {d.ecriture_id for d in decisions.lister_decisions(dossier.id)}
        moyens = propositions.moyens_de_paiement([e.id for e in ecritures])
        comptes = (configuration_de(dossier).comptes_categories_statut(), comptes_pack)
        reprise = reprendre(
            dossier.id,
            ecritures,
            decidees,
            moyens,
            pipeline,
            comptes,
            ledger.periodes_closes(dossier.id),
            dossier.regime_tva,
        )
        total += len(reprise.reclassements)
        print(
            f"{dossier.id} : {reprise.candidates} au 471, "
            f"{len(reprise.reclassements)} reclassée(s) ; {_vers(reprise.reclassements)}",
            flush=True,
        )
        if arguments.appliquer:
            for od in reprise.reclassements:
                ledger.enregistrer(od)
    mode = "écrites" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} OD {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
