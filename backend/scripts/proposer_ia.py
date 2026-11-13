"""Fait proposer une catégorie par Claude aux opérations à trancher d'un dossier (AXE-888).

À lancer avant une démo : les propositions sont enregistrées, et l'écran les
montre ensuite sans aucun appel en direct. Les libellés partent pseudonymisés,
dédoublonnés, par lots. Un libellé déjà envoyé ne repart jamais.

Simulation par défaut : compte les libellés à envoyer, sans aucun appel.
`--appliquer` appelle Claude (clé `ANTHROPIC_API_KEY` requise) et enregistre.
Le modèle vient de `ANTHROPIC_MODEL`, sinon Claude Fable 5.2 ; `--modele`
l'emporte. Une clé non limitée à un workspace exige `ANTHROPIC_WORKSPACE_ID`.
Le plafond de dépense (1 $ par défaut) arrête les appels dès qu'il est atteint.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/proposer_ia.py --dossier DOSSIER_ID
    python scripts/proposer_ia.py --dossier DOSSIER_ID --appliquer --plafond-usd 1
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

from axelcompta.categorize.llm import VERSION_PROMPT, DemandeIa, schema_reponse
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId
from axelcompta.ledger.banque import montant_bancaire
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.pseudonymize.fournisseur_anthropic import (
    BudgetDepasse,
    FournisseurAnthropic,
    ReponseInutilisable,
    WorkspaceRequis,
    modele_configure,
)
from axelcompta.pseudonymize.llm import JournalPrompts
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.workflow.propositions_ia import (
    categories_proposables,
    demandes_a_envoyer,
    par_lots,
    proposer,
)
from axelcompta.workflow.propositions_ia_postgres import PostgresPropositionsIa
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.reclassement import projeter
from axelcompta.workflow.revue import COMPTE_ATTENTE


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--dossier", required=True)
    parseur.add_argument(
        "--appliquer", action="store_true", help="appeler Claude (sinon simulation)"
    )
    parseur.add_argument("--plafond-usd", type=float, default=1.0)
    parseur.add_argument(
        "--modele",
        default=None,
        help="modèle Claude (défaut : ANTHROPIC_MODEL, sinon claude-fable-5-2)",
    )
    arguments = parseur.parse_args()
    arguments.modele = modele_configure(arguments.modele)
    if arguments.appliquer and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY n'est pas définie : rien n'est envoyé.")

    engine = engine_depuis_env()
    dossier = PostgresDossierRepository(engine).obtenir(DossierId(arguments.dossier))
    if dossier is None:
        raise SystemExit(f"dossier inconnu : {arguments.dossier}")
    ecritures = PostgresLedgerService(engine).grand_livre(dossier.id)
    exclues = annulees(ecritures)
    a_trancher = [
        e
        for e in projeter(ecritures)
        if e.id not in exclues and any(x.compte == COMPTE_ATTENTE for x in e.lignes)
    ]
    moyens = PostgresPropositionRepository(engine).moyens_de_paiement([e.id for e in a_trancher])
    cache = PostgresPropositionsIa(engine)
    demandes = demandes_a_envoyer(
        ((e.libelle, montant_bancaire(e), moyens.get(e.id)) for e in a_trancher),
        cache.lister(dossier.id, VERSION_PROMPT),
    )
    nombre = f"{len(a_trancher)} opération(s) à trancher"
    print(f"{dossier.id} : {nombre}, {len(demandes)} libellé(s) à envoyer")
    if not arguments.appliquer or not demandes:
        return 0
    return _envoyer(dossier, demandes, cache, arguments)


def _envoyer(
    dossier: Dossier,
    demandes: list[DemandeIa],
    cache: PostgresPropositionsIa,
    arguments: argparse.Namespace,
) -> int:
    categories = categories_proposables(charger_compte_par_categorie())
    fournisseur = FournisseurAnthropic(
        schema_reponse(categories), JournalPrompts(), arguments.plafond_usd, modele=arguments.modele
    )
    enregistrees = 0
    for lot in par_lots(demandes):
        try:
            contexte = (arguments.modele, VERSION_PROMPT, datetime.now(UTC))
            propositions = proposer(dossier, lot, fournisseur, categories, contexte)
        except BudgetDepasse as erreur:
            print(f"Arrêt : {erreur}")
            break
        except WorkspaceRequis as erreur:
            raise SystemExit(str(erreur)) from erreur
        except ReponseInutilisable as erreur:
            print(f"Lot ignoré, laissé à l'humain : {erreur}")
            continue
        cache.enregistrer(propositions)
        enregistrees += len(propositions)
    print(f"{enregistrees} proposition(s) enregistrée(s), dépense {fournisseur.depense_usd:.4f} $")
    return 0


if __name__ == "__main__":
    sys.exit(main())
