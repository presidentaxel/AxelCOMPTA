"""Écrit le CA des mois sans Rollee depuis les récapitulatifs de plateforme (AXE-801).

Pour chaque dossier relié à une fiche d'import : chaque récapitulatif mensuel
lu et juste au centime (Uber, Bolt…) devient la recette du mois (467x contre
706, 44571, 708, 6222), et les virements de la plateforme du mois encore au
471 soldent la créance. Un mois que Rollee couvre n'est pas touché.

Simulation par défaut : par dossier, les mois écrits, le CA HT et les
virements soldés. `--appliquer` écrit. Rejouable sans doublon.

Usage, depuis backend/ (DATABASE_URL défini) :

    python scripts/ecrire_recettes_recaps.py --tenant TENANT_DEMO
    python scripts/ecrire_recettes_recaps.py --tenant TENANT_DEMO --appliquer
"""

from __future__ import annotations

import argparse
import sys

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.ingestion.recettes_recaps import ecritures_du_mois, recap_depuis
from axelcompta.ingestion.settlements_plateforme_postgres import PostgresSettlements
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_plateformes
from axelcompta.stockage_documents import depot_documents
from axelcompta.tenants.fiches_import_postgres import PostgresFichesImport
from axelcompta.tenants.postgres import PostgresDossierRepository


def _ca_ht(ods: list[Ecriture]) -> int:
    return sum(lg.montant.centimes for od in ods for lg in od.lignes if lg.compte.startswith("70"))


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument("--appliquer", action="store_true", help="écrire (sinon simulation)")
    arguments = parseur.parse_args()

    engine = engine_depuis_env()
    tenant = TenantId(arguments.tenant)
    ledger = PostgresLedgerService(engine)
    settlements = PostgresSettlements(engine)
    fiches = PostgresFichesImport(engine, depot_documents())
    dossiers = {d.id: d for d in PostgresDossierRepository(engine).lister_par_tenant(tenant)}
    regimes = {p.nom: (p.motif, p.commission_tva_regime) for p in charger_plateformes()}
    total = 0
    for fiche in fiches.toutes(tenant):
        dossier = dossiers.get(fiche.dossier_id) if fiche.dossier_id else None
        if dossier is None or fiche.statut == "ignore" or fiche.annulee_le:
            continue
        documents = fiches.instantane(tenant, fiche.id).documents
        recaps = [
            r
            for d in documents
            if d.statut_traitement == "traite" and (r := recap_depuis(d.donnees or {}))
        ]
        if not recaps:
            continue
        rollee = {
            (s.settlement.platform, s.settlement.period_start.isoformat()[:7])
            for s in settlements.lister(dossier.id)
        }
        ecritures = list(ledger.grand_livre(dossier.id))
        ods: list[Ecriture] = []
        for recap in sorted(recaps, key=lambda r: (r.plateforme, r.mois)):
            nouvelles = ecritures_du_mois(
                dossier.id, recap, ecritures, regimes, rollee, dossier.tva_recettes_regime
            )
            ecritures += nouvelles
            ods += nouvelles
        soldes = [od for od in ods if od.id.endswith(":solde-plateforme")]
        total += len(ods)
        print(
            f"{dossier.id} {dossier.nom} : {len(recaps)} récapitulatif(s), "
            f"{len(ods) - len(soldes)} mois écrit(s), CA HT {_ca_ht(ods) / 100:.2f} €, "
            f"{len(soldes)} virement(s) soldé(s)",
            flush=True,
        )
        if arguments.appliquer:
            for od in ods:
                ledger.enregistrer(od)
    mode = "écrites" if arguments.appliquer else "à écrire (simulation)"
    print(f"Total : {total} OD {mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
