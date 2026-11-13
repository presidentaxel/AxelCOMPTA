"""L'étage LLM dans les tâches planifiées (AXE-887).

À chaque passage : relever les lots finis, soumettre les nouveaux, envoyer
les alertes de budget. Une fois par jour, les métriques du mois (doc 15).

Éteint par défaut. Il faut `AXELCOMPTA_LLM_ACTIF=1` et `ANTHROPIC_API_KEY`
(une clé par environnement, dans les secrets du serveur, jamais dans le
repo). Réglages facultatifs : `AXELCOMPTA_LLM_MODELE`,
`AXELCOMPTA_LLM_PLAFOND_CHAUFFEUR_USD`, `AXELCOMPTA_LLM_PLAFOND_GLOBAL_USD`.
La limite de dépense de la console Anthropic reste le dernier filet.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine

from axelcompta.categorize.llm import consignes_systeme, schema_reponse
from axelcompta.core.ids import TenantId
from axelcompta.core.metriques import METRIQUES
from axelcompta.ledger.banque import montant_bancaire
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.packs.vtc_demo import charger_compte_par_categorie
from axelcompta.pseudonymize.fournisseur_anthropic import (
    MODELE_PAR_DEFAUT,
    FournisseurLotsAnthropic,
)
from axelcompta.pseudonymize.llm import JournalPrompts
from axelcompta.tenants.branchements import choisir
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.orm import droits_membre
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.tags import etat_du_portefeuille, retenus
from axelcompta.tenants.tags_postgres import PostgresTagsRepository
from axelcompta.workflow.alertes_llm import AlerteLlm, nouvelles_alertes
from axelcompta.workflow.budget_llm import (
    Depenses,
    Lot,
    debut_du_mois,
    du_mois,
    llm_actif,
    plafonds_configures,
    soumis_le_jour,
)
from axelcompta.workflow.etage_llm import (
    HISTORIQUE,
    DepotsLlm,
    DossierATrancher,
    relever,
    soumettre,
)
from axelcompta.workflow.lots_llm_postgres import PostgresAlertesLlm, PostgresLotsLlm
from axelcompta.workflow.propositions_ia import categories_proposables
from axelcompta.workflow.propositions_ia_postgres import PostgresPropositionsIa
from axelcompta.workflow.propositions_postgres import PostgresPropositionRepository
from axelcompta.workflow.rappels_envoi import expediteur_de
from axelcompta.workflow.reclassement import projeter
from axelcompta.workflow.revue import COMPTE_ATTENTE


def operations_a_trancher(engine: Engine, dossier: Dossier) -> DossierATrancher:
    """Les opérations restées au compte d'attente : ce que règles et modèle
    n'ont pas imputé."""
    ecritures = PostgresLedgerService(engine).grand_livre(dossier.id)
    exclues = annulees(ecritures)
    attente = [
        e
        for e in projeter(ecritures)
        if e.id not in exclues and any(x.compte == COMPTE_ATTENTE for x in e.lignes)
    ]
    moyens = PostgresPropositionRepository(engine).moyens_de_paiement([e.id for e in attente])
    return DossierATrancher(
        dossier,
        tuple((e.libelle, montant_bancaire(e), moyens.get(e.id)) for e in attente),
    )


def _dossiers(engine: Engine) -> list[Dossier]:
    """Les dossiers qu'aucun tag n'exclut du classement automatique."""
    depot = PostgresDossierRepository(engine)
    tags = PostgresTagsRepository(engine)
    dossiers: list[Dossier] = []
    for tenant in depot.lister_tenants():
        du_tenant = depot.lister_par_tenant(tenant.id)
        dossiers += retenus(du_tenant, etat_du_portefeuille(tags, tenant.id), "categorisation")
    return dossiers


def _a_relire(
    dossiers: Sequence[Dossier], lots: Sequence[Lot], maintenant: datetime
) -> list[Dossier]:
    """Pas la peine de relire le grand livre d'un dossier déjà passé aujourd'hui."""
    en_cours = {lot.dossier_id for lot in lots if lot.statut == "soumis"}
    return [
        d
        for d in dossiers
        if d.id not in en_cours and not soumis_le_jour(lots, d.id, maintenant.date())
    ]


def passer_llm(engine: Engine, maintenant: datetime) -> list[str]:
    if not llm_actif():
        return []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ["llm : ANTHROPIC_API_KEY absente, rien n'est envoyé"]
    categories = categories_proposables(charger_compte_par_categorie())
    fournisseur = FournisseurLotsAnthropic(
        schema_reponse(categories),
        consignes_systeme(categories),
        JournalPrompts(),
        modele=os.environ.get("AXELCOMPTA_LLM_MODELE", MODELE_PAR_DEFAUT),
    )
    depots = DepotsLlm(PostgresLotsLlm(engine), PostgresPropositionsIa(engine))
    plafonds = plafonds_configures()
    lignes = relever(depots, fournisseur, categories, maintenant)
    dossiers = _dossiers(engine)
    lots = depots.lots.lister(maintenant - HISTORIQUE)
    a_trancher = [operations_a_trancher(engine, d) for d in _a_relire(dossiers, lots, maintenant)]
    lignes += soumettre(depots, fournisseur, a_trancher, plafonds, maintenant)
    par_tenant: dict[TenantId, int] = {}
    for dossier in dossiers:
        par_tenant[dossier.tenant_id] = par_tenant.get(dossier.tenant_id, 0) + 1
    alertes = nouvelles_alertes(
        depots.lots.lister(debut_du_mois(maintenant)),
        par_tenant,
        plafonds,
        PostgresAlertesLlm(engine),
        maintenant,
    )
    for alerte in alertes:
        lignes.append(f"llm alerte : {_prevenir(engine, alerte)}")
    return lignes


def _admins(engine: Engine, tenant_id: TenantId) -> list[str]:
    with engine.connect() as connexion:
        return [
            str(email)
            for email in connexion.execute(
                select(droits_membre.c.email).where(
                    droits_membre.c.tenant_id == str(tenant_id), droits_membre.c.role == "admin"
                )
            ).scalars()
        ]


def _prevenir(engine: Engine, alerte: AlerteLlm) -> str:
    """Cabinet : un mail à ses admins par son SMTP par défaut. Global et
    anomalies : Sentry (erreur à 100 % du budget global)."""
    if alerte.tenant_id is None:
        _sentry(alerte.texte, "error" if alerte.grave else "warning")
        return f"{alerte.texte} (Sentry)"
    smtp = choisir(PostgresBranchements(engine).lister(alerte.tenant_id), "mail", None)
    admins = _admins(engine, alerte.tenant_id)
    if smtp is None or not admins:
        return f"{alerte.texte} (aucun SMTP ou aucun admin : non envoyée)"
    try:
        expediteur = expediteur_de(smtp)
        for admin in admins:
            expediteur.envoyer(admin, "AxeLCompta : budget de l'IA", alerte.texte)
    except Exception as exc:  # noqa: BLE001 — l'alerte reste notée, le passage continue
        return f"{alerte.texte} (envoi en échec : {type(exc).__name__})"
    return f"{alerte.texte} (mail à {len(admins)} admin(s))"


def _sentry(message: str, niveau: str) -> None:
    try:
        import sentry_sdk
    except ImportError:
        return
    sentry_sdk.capture_message(message, level=niveau)  # type: ignore[arg-type]


def mesurer_llm(lots: Sequence[Lot], maintenant: datetime) -> list[str]:
    """Doc 15 : coût du mois, coût moyen par chauffeur, taux de cache."""
    du_mois_ = du_mois(lots, maintenant)
    depenses = Depenses.du_mois(du_mois_, maintenant)
    chauffeurs = len(depenses.par_dossier)
    entree = sum(lot.jetons_entree for lot in du_mois_)
    part_cache = round(100 * sum(lot.jetons_cache for lot in du_mois_) / entree, 1) if entree else 0
    moyenne = depenses.globale / chauffeurs if chauffeurs else 0.0
    METRIQUES.jauger("llm_cout_mois_usd", round(depenses.globale, 4))
    METRIQUES.jauger("llm_cout_moyen_chauffeur_usd", round(moyenne, 4))
    METRIQUES.jauger("llm_libelles_mois", sum(len(lot.cles) for lot in du_mois_))
    METRIQUES.jauger("llm_part_cache", part_cache)
    METRIQUES.jauger(
        "llm_lots_en_echec_mois", sum(1 for lot in du_mois_ if lot.statut in ("echec", "refus"))
    )
    return [
        f"llm : {depenses.globale:.2f} $ ce mois-ci, {chauffeurs} chauffeur(s), "
        f"{moyenne:.3f} $ en moyenne, {part_cache:g} % lu en cache"
    ]
