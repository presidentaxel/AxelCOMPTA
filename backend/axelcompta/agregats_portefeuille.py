"""Réchauffe et vérifie les agrégats gardés du portefeuille (AXE-566).

Composition root comme `notifier.py` (doc 18). La page Entreprises lit les
agrégats en base (`agregats_dossier`) ; ce module sert à deux choses que les
requêtes ne doivent pas faire.

`--recalculer` remplit la table : à lancer une fois après la migration
`e7b3d9a15c42`, sinon la première ouverture de chaque portefeuille calcule
tous ses dossiers. Sans `--tout`, il ne recalcule que les dossiers jamais
calculés ou périmés ; avec, il refait tout (après avoir monté
`VERSION_CALCUL`, par exemple). Rejouable à tout moment, même pendant que
l'API tourne : un dossier modifié pendant le calcul n'est pas écrasé.

`--verifier` ne modifie rien. Il recalcule chaque dossier dont l'agrégat est
gardé et à jour, et signale ceux qui diffèrent : une invalidation manquée.
Un dossier périmé n'est pas un écart, il sera recalculé à la prochaine
ouverture. Un dossier modifié pendant la vérification non plus.

Usage, depuis backend/ (DATABASE_URL défini, le propriétaire de la base) :

    python -m axelcompta.agregats_portefeuille --tenant <tenant_id> --recalculer
    python -m axelcompta.agregats_portefeuille --tenant <tenant_id> --verifier
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from axelcompta.api.routes import calculer_agregat
from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import TenantId
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.agregats import AgregatsRepository, AgregatStocke
from axelcompta.tenants.agregats_postgres import PostgresAgregatsRepository
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.provisions_cloture import ProvisionsClotureRepository
from axelcompta.tenants.provisions_cloture_postgres import PostgresProvisionsClotureRepository
from axelcompta.workflow.decisions import DecisionRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository


@dataclass(frozen=True, slots=True)
class Divergence:
    dossier_id: str
    gardee: AgregatStocke
    recalculee: AgregatStocke


@dataclass(frozen=True, slots=True)
class Rapport:
    a_jour: int  # gardés, à jour, et égaux au recalcul
    perimes: int  # jamais calculés ou périmés : rien à vérifier
    modifies_pendant: int  # écrits pendant la vérification : le recalcul ne dit rien
    divergences: tuple[Divergence, ...]


def verifier(
    dossiers: Sequence[Dossier],
    base: LedgerService,
    decisions: DecisionRepository,
    provisions: ProvisionsClotureRepository,
    agregats: AgregatsRepository,
) -> Rapport:
    """Lecture seule : rien n'est enregistré, même pour un dossier périmé."""
    lignes = agregats.lire([dossier.id for dossier in dossiers])
    a_jour = perimes = modifies = 0
    divergences: list[Divergence] = []
    for dossier in dossiers:
        ligne = lignes.get(dossier.id)
        if ligne is None or ligne.valeur is None:
            perimes += 1
            continue
        recalculee = calculer_agregat(dossier, base, decisions, provisions)
        if recalculee == ligne.valeur:
            a_jour += 1
            continue
        # Un écart n'en est un que si la ligne n'a pas bougé pendant le calcul.
        relue = agregats.lire([dossier.id]).get(dossier.id)
        if relue is None or relue.valeur is None or relue.version != ligne.version:
            modifies += 1
        else:
            divergences.append(Divergence(dossier.id, ligne.valeur, recalculee))
    return Rapport(a_jour, perimes, modifies, tuple(divergences))


def recalculer(
    dossiers: Sequence[Dossier],
    base: LedgerService,
    decisions: DecisionRepository,
    provisions: ProvisionsClotureRepository,
    agregats: AgregatsRepository,
    tout: bool = False,
) -> int:
    """Retourne le nombre de dossiers dont l'agrégat a été (re)gardé."""
    lignes = agregats.lire([dossier.id for dossier in dossiers])
    gardes = 0
    for dossier in dossiers:
        ligne = lignes.get(dossier.id)
        if not tout and ligne is not None and ligne.valeur is not None:
            continue
        valeur = calculer_agregat(dossier, base, decisions, provisions)
        version = None if ligne is None else ligne.version
        if agregats.enregistrer(dossier.tenant_id, dossier.id, valeur, version):
            gardes += 1
    return gardes


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tenant", required=True)
    parseur.add_argument("--dossier", help="un seul dossier du portefeuille")
    action = parseur.add_mutually_exclusive_group(required=True)
    action.add_argument("--recalculer", action="store_true")
    action.add_argument("--verifier", action="store_true")
    parseur.add_argument(
        "--tout", action="store_true", help="avec --recalculer : même les dossiers à jour"
    )
    args = parseur.parse_args()

    engine = engine_depuis_env()
    dossiers = PostgresDossierRepository(engine).lister_par_tenant(TenantId(args.tenant))
    if args.dossier:
        dossiers = tuple(d for d in dossiers if d.id == args.dossier)
    depots = (
        PostgresLedgerService(engine),
        PostgresDecisionRepository(engine),
        PostgresProvisionsClotureRepository(engine),
        PostgresAgregatsRepository(engine),
    )
    if args.recalculer:
        print(f"{recalculer(dossiers, *depots, tout=args.tout)} dossier(s) recalculé(s)")
        return 0
    rapport = verifier(dossiers, *depots)
    print(
        f"{rapport.a_jour} à jour, {rapport.perimes} périmé(s) ou jamais calculé(s), "
        f"{rapport.modifies_pendant} modifié(s) pendant la vérification, "
        f"{len(rapport.divergences)} écart(s)"
    )
    for ecart in rapport.divergences:
        print(f"ÉCART {ecart.dossier_id} : gardé {ecart.gardee} ≠ recalculé {ecart.recalculee}")
    return 1 if rapport.divergences else 0


if __name__ == "__main__":
    sys.exit(main())
