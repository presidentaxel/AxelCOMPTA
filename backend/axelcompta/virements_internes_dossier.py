"""Virements internes d'un dossier, repris à chaque passage (AXE-968).

Un chauffeur à plusieurs comptes (MK DRIVING : compte pro, enveloppes
Trésorerie, Impôts et TVA, Prélèvements à venir…) déplace son argent d'un
compte à l'autre. Les deux jambes s'annulent : ce sont des virements
internes, au 580. La synchro ne les reconnaît que si elles arrivent dans
le même lot ; Digifactory livre parfois la seconde un ou plusieurs jours
plus tard. Le passage horaire regarde donc tout le grand livre.

Composition root (doc 18) : lit le grand livre et les décisions, écrit les
OD `{S}:virement-interne` (`workflow.virement_interne`). Rejouable : une
jambe déjà au 580 n'est plus candidate.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.engine import Engine

from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.ledger.service import LedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.statuts import configuration_de
from axelcompta.workflow.decisions import DecisionRepository
from axelcompta.workflow.decisions_postgres import PostgresDecisionRepository
from axelcompta.workflow.reclassement import grand_livre_tranche
from axelcompta.workflow.virement_interne import Reprise, reprises, sous_comptes_ventiles


def reprise_du_dossier(
    dossier: Dossier,
    ledger: LedgerService,
    decisions: DecisionRepository,
    comptes_pack: dict[str, str],
    *,
    seulement_en_attente: bool,
) -> Reprise:
    """Les OD de virement interne à écrire pour ce dossier. Rien n'est écrit."""
    ecritures = ledger.grand_livre(dossier.id)
    vue = grand_livre_tranche(
        ecritures,
        decisions.lister_decisions(dossier.id),
        (configuration_de(dossier).comptes_categories_statut(), comptes_pack),
    )
    return reprises(
        vue,
        ledger.periodes_closes(dossier.id),
        sous_comptes=sous_comptes_ventiles(ecritures),
        seulement_en_attente=seulement_en_attente,
    )


def reprendre_dossiers(engine: Engine, dossiers: Sequence[Dossier]) -> str:
    """Passage horaire, câblage Postgres."""
    return reprendre(
        dossiers,
        PostgresLedgerService(engine),
        PostgresDecisionRepository(engine),
        charger_compte_par_categorie(),
    )


def reprendre(
    dossiers: Sequence[Dossier],
    ledger: LedgerService,
    decisions: DecisionRepository,
    comptes_pack: dict[str, str],
) -> str:
    """Seulement les opérations encore au 471, jamais une opération qu'un
    humain a classée. Un dossier en échec n'arrête pas les autres."""
    paires, echecs = 0, 0
    for dossier in dossiers:
        try:
            reprise = reprise_du_dossier(
                dossier, ledger, decisions, comptes_pack, seulement_en_attente=True
            )
            for od in reprise.ecritures:
                ledger.enregistrer(od)
        except Exception:  # noqa: BLE001 — un dossier en échec n'arrête pas les autres
            echecs += 1
            continue
        paires += reprise.paires
    if not paires and not echecs:
        return ""
    texte = f"virements internes : {paires} paire(s) au 580"
    return f"{texte}, {echecs} dossier(s) en échec" if echecs else texte
