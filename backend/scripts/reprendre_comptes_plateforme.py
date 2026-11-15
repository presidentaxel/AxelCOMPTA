"""Reprend sur les comptes de l'expert les semaines de plateforme déjà écrites.

AXE-931. Le schéma de l'expert-comptable : un 467 par plateforme (4671 Uber,
4672 Bolt), les espèces en caisse (530), le hors course en 708, la
commission en 6222. Pour chaque OD de semaine déjà écrite (recette, solde,
frais), une OD `{S}:comptes-plateforme` déplace les montants des anciens
comptes vers les nouveaux (`ingestion.reprise_comptes_plateforme`). Rien
n'est supprimé.

Simulation par défaut : affiche ce qui serait écrit (des nombres, aucun
libellé). `--appliquer` écrit. Rejouable sans doublon.

Usage, depuis backend/ (DATABASE_URL défini, migrations appliquées) :

    python scripts/reprendre_comptes_plateforme.py --dossier DOSSIER_ID
    python scripts/reprendre_comptes_plateforme.py --tenant TENANT --appliquer
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.reprise_comptes_plateforme import reprises
from axelcompta.ledger.models import Ecriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository


def _dossiers(
    depot: PostgresDossierRepository, arguments: argparse.Namespace
) -> tuple[Dossier, ...]:
    if arguments.dossier:
        dossier = depot.obtenir(DossierId(arguments.dossier))
        if dossier is None:
            raise SystemExit(f"dossier inconnu : {arguments.dossier}")
        return (dossier,)
    return depot.lister_par_tenant(TenantId(arguments.tenant))


def _mouvements(ecritures: list[Ecriture]) -> str:
    """« 467 → 4671 : 12 345,67 € » pour chaque déplacement."""
    totaux: Counter[str] = Counter()
    for od in ecritures:
        for cible, origine in zip(od.lignes[::2], od.lignes[1::2], strict=True):
            montant = (
                cible.montant.centimes if cible.sens is Sens.DEBIT else -cible.montant.centimes
            )
            totaux[f"{origine.compte} → {cible.compte}"] += montant
    return " ; ".join(
        f"{k} : {v / 100:,.2f} €".replace(",", " ").replace(".", ",")
        for k, v in sorted(totaux.items())
    )


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cible = parseur.add_mutually_exclusive_group(required=True)
    cible.add_argument("--dossier")
    cible.add_argument("--tenant")
    parseur.add_argument("--appliquer", action="store_true", help="écrire (sinon simulation)")
    arguments = parseur.parse_args()

    engine = engine_depuis_env()
    ledger = PostgresLedgerService(engine)
    total = 0
    for dossier in _dossiers(PostgresDossierRepository(engine), arguments):
        a_ecrire = reprises(ledger.grand_livre(dossier.id), ledger.periodes_closes(dossier.id))
        total += len(a_ecrire)
        if a_ecrire:
            print(f"{dossier.id} : {len(a_ecrire)} OD ; {_mouvements(a_ecrire)}", flush=True)
        if arguments.appliquer:
            for od in a_ecrire:
                ledger.enregistrer(od)
    mode = "écrites" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} OD {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
