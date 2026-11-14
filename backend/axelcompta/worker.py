"""Worker de la file de jobs (ADR-002, AXE-845).

Le bouton « Synchroniser » d'Entreprises dépose une demande ; ce worker, qui
tourne avec le rôle propriétaire (comme les tâches planifiées), l'exécute :

1. crée les dossiers que le gestionnaire a acceptés (« Ajouter »), d'après
   une lecture Sirene fraîche, avec le tag `chauffeur` si l'activité est VTC ;
2. repère les contacts Digifactory sans dossier et les propose ;
3. synchronise les dossiers du portefeuille (exclusions par tag comprises),
   puis préchauffe les caches.

Le résumé (« 1 dossier créé, 2 chauffeurs proposés, 148 opérations
reçues ») s'affiche sous le bouton. Lancé chaque minute par le planificateur :

    python -m axelcompta.worker
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from axelcompta.core.db import engine_depuis_env
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.jobs.file import (
    TYPE_IMPORT_DOSSIERS,
    TYPE_RAPPELS,
    TYPE_RAPPROCHEMENT_ROLLEE,
    TYPE_ROLLEE,
    TYPE_SYNCHRO,
    Job,
)
from axelcompta.jobs.postgres import FilePostgres
from axelcompta.modeles_distants import assurer_modele
from axelcompta.nouveaux_contacts import (
    LireFiche,
    Proposition,
    contacts_sans_dossier,
    fiche_sirene,
    proposer,
)
from axelcompta.plateformes_rollee import suivi_postgres, traiter_evenements
from axelcompta.rappels import envoyer
from axelcompta.rapprochement_rollee_service import rapprocher_maintenant
from axelcompta.synchro_digifactory import (
    TYPE_DIGIFACTORY,
    ResultatDossier,
    client_digifactory,
    synchroniser_portefeuille,
)
from axelcompta.tenants.branchements import Branchement
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.contacts_proposes import ContactsProposesRepository, PropositionStockee
from axelcompta.tenants.contacts_proposes_postgres import PostgresContactsProposes
from axelcompta.tenants.import_dossiers import rapport as rapport_import
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.tenants.tags import (
    POSE_PAR_IMPORT,
    TAG_CHAUFFEUR,
    TagsRepository,
    etat_du_portefeuille,
    exclus,
    retenus,
    tag_depuis_naf,
)
from axelcompta.tenants.tags_postgres import PostgresTagsRepository

Contacts = Mapping[str, Mapping[str, object]]
# AXE-872 : un contact lu par un branchement Digifactory qui n'est pas celui
# par défaut porte son identifiant ; le dossier créé y est rattaché.
CLE_BRANCHEMENT = "_branchement"
Synchroniser = Callable[[tuple[Dossier, ...], frozenset[DossierId]], list[ResultatDossier]]


@dataclass(frozen=True, slots=True)
class Dependances:
    dossiers: DossierRepository
    contacts_proposes: ContactsProposesRepository
    tags: TagsRepository
    lire_contacts: Callable[[TenantId], Contacts]
    lire_fiche: LireFiche
    synchroniser: Synchroniser
    prechauffer: Callable[[tuple[Dossier, ...]], int]
    # AXE-808 : une passe d'envoi des rappels ; bilan par statut.
    envoyer_rappels: Callable[[], dict[str, int]] | None = None
    # AXE-872 : rattache un dossier créé à son branchement Digifactory.
    choisir_branchement: Callable[[TenantId, DossierId, str], None] | None = None
    # AXE-820 : traite les webhooks Rollee gardés d'un portefeuille.
    traiter_rollee: Callable[[TenantId], str] | None = None
    # AXE-918 : bouton « Rapprocher Rollee » ; bilan en nombres.
    rapprocher_rollee: Callable[[TenantId], str] | None = None


def _stockee(proposition: Proposition, maintenant: datetime) -> PropositionStockee:
    dossier = proposition.dossier
    return PropositionStockee(
        contact_nr=proposition.contact_nr,
        nom=proposition.nom,
        siren=proposition.siren,
        forme=dossier.forme_juridique if dossier else None,
        exercice_debut=dossier.exercice_debut if dossier else None,
        code_naf=dossier.code_naf if dossier else None,
        avertissements=proposition.avertissements,
        cessee=dossier is None,
        detecte_le=maintenant,
    )


def _contacts_avec_dossier(deps: Dependances, tenant_id: TenantId) -> set[str]:
    return {d.contact_nr for d in deps.dossiers.lister_par_tenant(tenant_id) if d.contact_nr}


def creer_les_acceptes(
    tenant_id: TenantId, contacts: Contacts, deps: Dependances, aujourd_hui: date
) -> list[Dossier]:
    """Les contacts « Ajouter » sans dossier deviennent des dossiers."""
    decisions = deps.contacts_proposes.decisions(tenant_id)
    connus = _contacts_avec_dossier(deps, tenant_id)
    crees = []
    for contact in contacts_sans_dossier(contacts, connus):
        proposition = proposer(contact, deps.lire_fiche, aujourd_hui)
        if decisions.get(proposition.contact_nr) != "ajouter" or proposition.dossier is None:
            continue
        dossier = replace(proposition.dossier, tenant_id=tenant_id)
        deps.dossiers.enregistrer(dossier)
        origine = contacts.get(proposition.contact_nr, {}).get(CLE_BRANCHEMENT)
        if isinstance(origine, str) and deps.choisir_branchement is not None:
            deps.choisir_branchement(tenant_id, dossier.id, origine)
        if tag_depuis_naf(dossier.code_naf) == TAG_CHAUFFEUR:
            deps.tags.poser(
                tenant_id, dossier.id, TAG_CHAUFFEUR, POSE_PAR_IMPORT, datetime.now(UTC)
            )
        crees.append(dossier)
    return crees


def detecter(
    tenant_id: TenantId, contacts: Contacts, deps: Dependances, aujourd_hui: date
) -> list[Proposition]:
    """Les contacts sans dossier, proposés (remplace les propositions d'avant)."""
    connus = _contacts_avec_dossier(deps, tenant_id)
    propositions = [
        proposer(contact, deps.lire_fiche, aujourd_hui)
        for contact in contacts_sans_dossier(contacts, connus)
    ]
    maintenant = datetime.now(UTC)
    deps.contacts_proposes.remplacer_propositions(
        tenant_id, [_stockee(p, maintenant) for p in propositions]
    )
    return propositions


def detecter_portefeuilles(deps: Dependances, aujourd_hui: date) -> list[str]:
    """Passage planifié : propose les nouveaux contacts de chaque portefeuille
    branché sur Digifactory (au moins un dossier avec un contact)."""
    lignes = []
    for tenant in deps.dossiers.lister_tenants():
        if not any(d.contact_nr for d in deps.dossiers.lister_par_tenant(tenant.id)):
            continue
        contacts = deps.lire_contacts(tenant.id)
        nouveaux = [p for p in detecter(tenant.id, contacts, deps, aujourd_hui) if p.dossier]
        lignes.append(f"{tenant.id} nouveaux chauffeurs à valider : {len(nouveaux)}")
    return lignes


def synchroniser_portefeuille_suivi(
    tenant_id: TenantId, deps: Dependances, aujourd_hui: date
) -> str:
    """Les trois étapes, et le résumé affiché sous le bouton."""
    contacts = deps.lire_contacts(tenant_id)
    crees = creer_les_acceptes(tenant_id, contacts, deps, aujourd_hui)
    propositions = detecter(tenant_id, contacts, deps, aujourd_hui)
    tous = deps.dossiers.lister_par_tenant(tenant_id)
    etat = etat_du_portefeuille(deps.tags, tenant_id)
    resultats = deps.synchroniser(
        retenus(tous, etat, "synchro"), exclus(tous, etat, "categorisation")
    )
    deps.prechauffer(tous)
    return resume(len(crees), propositions, resultats)


def _quantite(nombre: int, singulier: str, pluriel: str) -> str:
    return f"{nombre} {singulier if nombre <= 1 else pluriel}"


def resume(crees: int, propositions: list[Proposition], resultats: list[ResultatDossier]) -> str:
    """« 1 dossier créé, 2 nouveaux chauffeurs à valider, 148 opérations reçues »."""
    recues = sum(r.rapport.nouvelles for r in resultats if r.rapport)
    erreurs = sum(1 for r in resultats if r.erreur)
    nouveaux = sum(1 for p in propositions if p.dossier is not None)
    morceaux = []
    if crees:
        morceaux.append(_quantite(crees, "dossier créé", "dossiers créés"))
    if nouveaux:
        morceaux.append(
            _quantite(nouveaux, "nouveau chauffeur à valider", "nouveaux chauffeurs à valider")
        )
    morceaux.append(_quantite(recues, "opération reçue", "opérations reçues"))
    if erreurs:
        morceaux.append(_quantite(erreurs, "dossier en erreur", "dossiers en erreur"))
    return ", ".join(morceaux)


def importer_dossiers(job: Job, dossiers: DossierRepository) -> str:
    """AXE-809 : les lignes du fichier, revalidées contre le portefeuille du
    moment (un second dépôt ne crée rien de plus), créées dans un lot."""
    tenant_id = TenantId(job.tenant_id)
    lignes = json.loads(job.payload).get("lignes", [])
    existants = [d.id for d in dossiers.lister_par_tenant(tenant_id)]
    resultat = rapport_import(tenant_id, lignes, existants)
    crees = dossiers.enregistrer_lot(resultat.valides)
    morceaux = [_quantite(crees, "dossier créé", "dossiers créés")]
    if resultat.en_erreur:
        morceaux.append(_quantite(resultat.en_erreur, "ligne écartée", "lignes écartées"))
    return ", ".join(morceaux)


def resume_envois(bilan: dict[str, int]) -> str:
    """« 2 rappels envoyés, 1 en échec » : ce qui s'affiche au gestionnaire."""
    envoyes, echecs = bilan.get("envoye", 0), bilan.get("echec", 0)
    morceaux = [_quantite(envoyes, "rappel envoyé", "rappels envoyés")]
    if echecs:
        morceaux.append(_quantite(echecs, "en échec", "en échec"))
    if bilan.get("en_attente", 0):
        morceaux.append(_quantite(bilan["en_attente"], "à réessayer", "à réessayer"))
    return ", ".join(morceaux)


def executer_job(job: Job, deps: Dependances, aujourd_hui: date) -> str:
    if job.type == TYPE_IMPORT_DOSSIERS:
        return importer_dossiers(job, deps.dossiers)
    if job.type == TYPE_RAPPELS and deps.envoyer_rappels is not None:
        return resume_envois(deps.envoyer_rappels())
    if job.type == TYPE_ROLLEE and deps.traiter_rollee is not None:
        return deps.traiter_rollee(TenantId(job.tenant_id))
    if job.type == TYPE_RAPPROCHEMENT_ROLLEE and deps.rapprocher_rollee is not None:
        return deps.rapprocher_rollee(TenantId(job.tenant_id))
    if job.type != TYPE_SYNCHRO:
        raise ValueError(f"type de job non pris en charge : {job.type}")
    return synchroniser_portefeuille_suivi(TenantId(job.tenant_id), deps, aujourd_hui)


async def contacts_du_portefeuille(
    branchements: list[Branchement],
) -> dict[str, dict[str, object]]:
    """AXE-872 : les contacts de chaque branchement Digifactory actif, celui
    par défaut d'abord. Aucun branchement : le jeton de l'environnement."""
    actifs = sorted((b for b in branchements if b.actif), key=lambda b: not b.par_defaut)
    sources: list[Branchement | None] = list(actifs) or [None]
    tous: dict[str, dict[str, object]] = {}
    for branchement in sources:
        client = client_digifactory(branchement)
        try:
            brut = await client.contacts()
        finally:
            await client.aclose()
        for nr, contact in brut.items():
            if not isinstance(contact, dict) or str(nr) in tous:
                continue
            secondaire = branchement is not None and not branchement.par_defaut
            tous[str(nr)] = (
                {**contact, CLE_BRANCHEMENT: branchement.id}
                if secondaire and branchement
                else contact
            )
    return tous


def dependances_reelles() -> Dependances:
    engine = engine_depuis_env()
    from axelcompta.api.routes import prechauffer_caches

    branchements = PostgresBranchements(engine)

    async def contacts(tenant_id: TenantId) -> dict[str, dict[str, object]]:
        return await contacts_du_portefeuille(
            [b for b in branchements.lister(tenant_id) if b.type == TYPE_DIGIFACTORY]
        )

    return Dependances(
        dossiers=PostgresDossierRepository(engine),
        contacts_proposes=PostgresContactsProposes(engine),
        tags=PostgresTagsRepository(engine),
        lire_contacts=lambda tenant_id: asyncio.run(contacts(tenant_id)),
        lire_fiche=fiche_sirene,
        synchroniser=lambda d, s: synchroniser_portefeuille(engine, d, s),
        prechauffer=lambda d: prechauffer_caches(engine, d),
        envoyer_rappels=lambda: envoyer(engine, datetime.now(UTC)),
        choisir_branchement=lambda t, d, b: branchements.choisir_pour_dossier(
            t, d, TYPE_DIGIFACTORY, b
        ),
        traiter_rollee=lambda t: traiter_evenements(suivi_postgres(engine), t),
        rapprocher_rollee=lambda t: rapprocher_maintenant(engine, t),
    )


def main() -> int:
    """Une passe : toutes les demandes en attente, puis s'arrête (le
    planificateur relance chaque minute, sous `flock`)."""
    assurer_modele()
    file = FilePostgres(engine_depuis_env())
    deps = dependances_reelles()
    while (job := file.prendre("worker")) is not None:
        try:
            resultat = executer_job(job, deps, date.today())
        except Exception as exc:  # noqa: BLE001 — l'erreur est gardée et affichée
            file.echouer(job.id, f"{type(exc).__name__}: {exc}")
            print(f"[{job.id}] échec : {exc}", flush=True)
        else:
            file.terminer(job.id, resultat)
            print(f"[{job.id}] {resultat}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
