"""Reprend en virement interne (580) les mouvements entre enveloppes déjà écrits.

AXE-930. Certaines banques à enveloppes (MK DRIVING) montrent les deux jambes
d'un mouvement sur le même compte, avec le même libellé (« cotisation
URSSAF » −50 € / +50 €). Avant AXE-930, elles passaient pour des charges.
Pour chaque paire trouvée, une OD `{S}:virement-interne` déplace chaque jambe
vers le 580 (`workflow.virement_interne`) ; l'opération bancaire ne change
pas. Une paire dont une jambe porte de la TVA est laissée, et comptée.

Simulation par défaut : affiche ce qui serait écrit (des nombres, aucun
libellé). `--appliquer` écrit. Rejouable sans doublon.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/reprendre_virements_internes.py --dossier DOSSIER_ID
    python scripts/reprendre_virements_internes.py --tenant TENANT --appliquer
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
from axelcompta.tenants.tags import etat_du_portefeuille, retenus
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.virements_internes_dossier import reprise_du_dossier
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository


def _dossiers(
    depot: PostgresDossierRepository,
    tags: PostgresTagsRepository,
    arguments: argparse.Namespace,
) -> tuple[Dossier, ...]:
    if arguments.dossier:
        dossier = depot.obtenir(DossierId(arguments.dossier))
        if dossier is None:
            raise SystemExit(f"dossier inconnu : {arguments.dossier}")
        return (dossier,)
    tenant_id = TenantId(arguments.tenant)
    # Un dossier qu'un tag exclut (société du gestionnaire, test, hors
    # périmètre) n'est pas touché ; `--dossier` le vise quand même.
    etat = etat_du_portefeuille(tags, tenant_id)
    return retenus(depot.lister_par_tenant(tenant_id), etat, "categorisation")


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
    dossiers = _dossiers(
        PostgresDossierRepository(engine), PostgresTagsRepository(engine), arguments
    )
    for dossier in dossiers:
        reprise = reprise_du_dossier(
            dossier, ledger, decisions, comptes_pack, seulement_en_attente=False
        )
        total += len(reprise.ecritures)
        if reprise.ecritures or reprise.avec_tva:
            print(
                f"{dossier.id} : {reprise.paires} paire(s), {len(reprise.ecritures)} OD, "
                f"{reprise.avec_tva} paire(s) laissée(s) (TVA)",
                flush=True,
            )
        if arguments.appliquer:
            for od in reprise.ecritures:
                ledger.enregistrer(od)
    mode = "écrites" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} OD {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
