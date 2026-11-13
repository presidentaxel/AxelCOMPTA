"""Relier les users Rollee existants à leurs dossiers (AXE-911).

Composition root : lit les users d'un branchement Rollee (profils et IBAN de
versement), les contacts et comptes Digifactory du portefeuille, l'e-mail du
compte chauffeur ; réduit tout en empreintes dès la lecture, puis appelle
`ingestion.rapprochement_rollee`. Rien en clair n'est gardé ni envoyé ailleurs.

Deux modes :

* simulation (par défaut) : le bilan, sans rien écrire ;
* application : les liens sûrs sont posés (`auto`, avec l'indice), les
  autres users vont dans la file « à choisir » du gestionnaire, qui est
  prévenu par mail s'il y en a de nouveaux.

L'écriture automatique n'est faite par les tâches planifiées que si
`AXELCOMPTA_ROLLEE_RAPPROCHEMENT=1`, posé après lecture du bilan de la
simulation en production.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from axelcompta.comptes import SupabaseCompteRepository, SupabaseConfig
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.comptes_rollee_postgres import PostgresComptesRollee
from axelcompta.ingestion.liens_rollee import AChoisir, Lien, LienDejaPris, LiensRollee
from axelcompta.ingestion.liens_rollee_postgres import PostgresLiensRollee
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
from axelcompta.ingestion.rapprochement_rollee import (
    DossierIndices,
    Issue,
    UserRollee,
    apercu,
    bilan,
    empreintes,
    normaliser_nom,
    rapprocher,
)
from axelcompta.plateformes_rollee import TYPE_ROLLEE, ServicesRollee, client_du_branchement
from axelcompta.prevenir_admins import prevenir_admins
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository

VARIABLE_ACTIF = "AXELCOMPTA_ROLLEE_RAPPROCHEMENT"


def rapprochement_actif() -> bool:
    return os.environ.get(VARIABLE_ACTIF) == "1"


def cle_empreintes() -> bytes:
    """Dérivée de la clé des intégrations : sans elle, les empreintes ne se
    recalculent pas, même en volant la base."""
    cle = os.environ.get("AXELCOMPTA_CLE_INTEGRATIONS")
    if not cle:
        raise RuntimeError("AXELCOMPTA_CLE_INTEGRATIONS manquante : rien n'est comparé")
    return hashlib.sha256(b"rapprochement-rollee:" + cle.encode()).digest()


async def _infos_compte(client: RolleeHttpClient, compte_id: str) -> tuple[dict[str, Any], str]:
    """Profil et IBAN d'un compte de plateforme. Un compte illisible ne bloque pas."""
    try:
        profil = await client.profil(compte_id)
    except Exception:  # noqa: BLE001 — Uber ou Bolt sans profil : on compare le reste
        profil = {}
    try:
        iban = str((await client.coordonnees_bancaires(compte_id)).get("iban") or "")
    except Exception:  # noqa: BLE001
        iban = ""
    return profil, iban


async def lire_user(client: RolleeHttpClient, brut: Mapping[str, Any], cle: bytes) -> UserRollee:
    """Un user Rollee, ses comptes de plateformes, réduits en empreintes."""
    user_id = str(brut["id"])
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    ibans, noms, emails, telephones, plateformes = [], [], [], [], []
    premier: tuple[str | None, str | None] = (None, None)
    for compte in await client.comptes(user_id):
        plateformes.append(str(compte.get("name") or compte.get("type") or "plateforme"))
        profil, iban = await _infos_compte(client, str(compte["id"]))
        prenom, nom = profil.get("first_name"), profil.get("last_name")
        if prenom or nom:
            noms.append(normaliser_nom(prenom, nom))
            premier = premier if premier != (None, None) else (prenom, nom)
        emails.append(profil.get("email"))
        telephones.append(profil.get("phone"))
        ibans.append(iban)
    return UserRollee(
        user_id,
        str(dossier) if dossier else None,
        empreintes(cle, ibans, noms, emails, telephones),
        apercu(premier[0], premier[1], plateformes, next((i for i in ibans if i), None)),
    )


# AXE-917 : un passage lit ~2 200 users (comptes, profil, IBAN). En série,
# plus de 10 minutes ; quelques appels à la fois restent polis avec Rollee.
APPELS_SIMULTANES = 8


async def lire_users(
    client: RolleeHttpClient, cle: bytes, seulement: str | None = None
) -> list[UserRollee]:
    bruts = [
        brut
        for brut in await client.utilisateurs()
        if "id" in brut and (seulement is None or str(brut["id"]) == seulement)
    ]
    limite = asyncio.Semaphore(APPELS_SIMULTANES)

    async def un(brut: Mapping[str, Any]) -> UserRollee:
        async with limite:
            return await lire_user(client, brut, cle)

    return list(await asyncio.gather(*(un(brut) for brut in bruts)))


@dataclass(frozen=True, slots=True)
class SourcesDossiers:
    """Ce qu'AxeL sait du chauffeur, en clair le temps de le hacher."""

    contacts: Mapping[str, Mapping[str, Any]]  # contact Digifactory par `nr`
    ibans: Mapping[str, Sequence[str]]  # IBAN des comptes Digifactory, par dossier
    emails: Mapping[str, str | None]  # e-mail du compte chauffeur, par dossier


def ibans_digifactory(payload: object) -> list[str]:
    """IBAN d'une réponse `GET /accounts/{contactNr}` (dict par compte ou liste)."""
    if isinstance(payload, Mapping):
        valeurs: list[object] = list(payload.values())
    elif isinstance(payload, list):
        valeurs = payload
    else:
        return []
    return [str(v["iban"]) for v in valeurs if isinstance(v, Mapping) and v.get("iban")]


def indices_dossier(dossier: Dossier, sources: SourcesDossiers, cle: bytes) -> DossierIndices:
    noms: list[str] = []
    contact = sources.contacts.get(str(dossier.contact_nr)) if dossier.contact_nr else None
    if contact and (contact.get("firstname") or contact.get("lastname")):
        noms.append(normaliser_nom(contact.get("firstname"), contact.get("lastname")))
    emails = [sources.emails.get(str(dossier.id))]
    if dossier.identite is not None:
        emails.append(dossier.identite.email)
        noms += [normaliser_nom(a.prenoms, a.nom) for a in dossier.identite.associes]
    return DossierIndices(
        str(dossier.id),
        empreintes(cle, sources.ibans.get(str(dossier.id), ()), noms, emails),
    )


@dataclass(frozen=True, slots=True)
class Passage:
    tenant_id: TenantId
    branchement_id: str
    maintenant: datetime
    partiel: bool = False  # un seul user (webhook) : le reste de la file est gardé


def appliquer(
    liens: LiensRollee, issues: Sequence[Issue], users: Sequence[UserRollee], passage: Passage
) -> list[AChoisir]:
    """Pose les liens sûrs ; met les autres dans la file. Rend les users
    nouvellement à choisir ou non trouvés (pour prévenir le gestionnaire).
    Un user écarté par le gestionnaire le reste."""
    apercus = {u.user_id: u.apercu for u in users}
    existants = liens.a_choisir(passage.tenant_id)
    ecartes = {a.rollee_user_id: a for a in existants if a.etat == "ecarte"}
    attente: list[AChoisir] = []
    for issue in issues:
        if issue.user_id in ecartes:
            attente.append(ecartes[issue.user_id])
            continue
        if issue.etat == "relie_auto" and issue.dossier_id is not None:
            lien = Lien(
                DossierId(issue.dossier_id),
                issue.user_id,
                passage.branchement_id,
                "auto",
                passage.maintenant,
                issue.indice,
            )
            try:
                liens.lier(lien)
                continue
            except LienDejaPris:
                pass  # posé entre-temps par quelqu'un d'autre : au gestionnaire
        etat = "non_trouve" if issue.etat == "non_trouve" else "a_choisir"
        attente.append(
            AChoisir(
                issue.user_id,
                passage.tenant_id,
                passage.branchement_id,
                etat,  # type: ignore[arg-type]
                issue.candidats,
                apercus[issue.user_id],
                passage.maintenant,
            )
        )
    vus = {i.user_id for i in issues}
    gardes = [
        a
        for a in existants
        if passage.partiel
        and a.branchement_id == passage.branchement_id
        and a.rollee_user_id not in vus
    ]
    liens.remplacer_a_choisir(passage.tenant_id, passage.branchement_id, [*gardes, *attente])
    deja = {a.rollee_user_id for a in existants}
    return [a for a in attente if a.rollee_user_id not in deja]


def resume(issues: Sequence[Issue]) -> str:
    compte = bilan(issues)
    return (
        f"{compte['relie_auto']} relié(s) automatiquement, {compte['a_choisir']} à choisir, "
        f"{compte['non_trouve']} non trouvé(s)"
    )


def trancher_tous(
    users: Sequence[UserRollee],
    dossiers: Sequence[DossierIndices],
    liens: Sequence[Lien],
    retires: frozenset[tuple[str, str]] = frozenset(),
) -> list[Issue]:
    poses = {x.rollee_user_id: str(x.dossier_id) for x in liens}
    return rapprocher(users, dossiers, poses, retires)


# --- Câblage : un portefeuille, ses branchements Rollee ----------------------


@dataclass
class DepotsRapprochement:
    services: ServicesRollee  # branchements Rollee et clients (jeton renouvelé gardé)
    liens: LiensRollee
    dossiers: DossierRepository
    sources: Callable[[TenantId, tuple[Dossier, ...]], Awaitable[SourcesDossiers]]
    prevenir: Callable[[TenantId, list[AChoisir]], str] | None = None


async def passer_tenant(
    depots: DepotsRapprochement,
    tenant_id: TenantId,
    ecrire: bool,
    maintenant: datetime,
    seulement: str | None = None,
) -> list[str]:
    """Un passage sur un portefeuille. `ecrire` faux : simulation, rien
    n'est écrit. `seulement` : un seul user (webhook d'un user inconnu)."""
    cle = cle_empreintes()
    dossiers = depots.dossiers.lister_par_tenant(tenant_id)
    sources = await depots.sources(tenant_id, dossiers)
    indices = [indices_dossier(d, sources, cle) for d in dossiers]
    rollee = [
        b
        for b in depots.services.branchements.lister(tenant_id)
        if b.type == TYPE_ROLLEE and b.actif
    ]
    lignes = []
    for branchement in rollee:
        client = client_du_branchement(depots.services, branchement)
        try:
            users = await lire_users(client, cle, seulement)
        finally:
            await client.aclose()
        issues = trancher_tous(
            users, indices, depots.liens.liens(tenant_id), depots.liens.paires_retirees(tenant_id)
        )
        mode = "" if ecrire else " (simulation : rien n'est écrit)"
        lignes.append(f"{tenant_id} / {branchement.nom} : {resume(issues)}{mode}")
        if not ecrire:
            continue
        passage = Passage(tenant_id, branchement.id, maintenant, seulement is not None)
        nouveaux = appliquer(depots.liens, issues, users, passage)
        if nouveaux and depots.prevenir is not None:
            lignes.append(f"{tenant_id} : {depots.prevenir(tenant_id, nouveaux)}")
    return lignes


async def sources_reelles(
    engine: Engine, tenant_id: TenantId, dossiers: tuple[Dossier, ...]
) -> SourcesDossiers:
    """Contacts et comptes Digifactory, e-mail du compte chauffeur. Une
    source en panne laisse ses indices vides : le reste compare quand même."""
    from axelcompta.synchro_digifactory import client_digifactory, repartir_par_branchement
    from axelcompta.worker import contacts_du_portefeuille

    branchements = PostgresBranchements(engine)
    try:
        contacts = await contacts_du_portefeuille(
            [b for b in branchements.lister(tenant_id) if b.type == "digifactory"]
        )
    except Exception:  # noqa: BLE001
        contacts = {}
    ibans: dict[str, list[str]] = {}
    for branchement, groupe in repartir_par_branchement(dossiers, branchements):
        client = client_digifactory(branchement)
        try:
            for dossier in groupe:
                if dossier.contact_nr:
                    with suppress(Exception):
                        ibans[str(dossier.id)] = ibans_digifactory(
                            await client.accounts(dossier.contact_nr)
                        )
        finally:
            await client.aclose()
    return SourcesDossiers(contacts, ibans, _emails_chauffeurs(dossiers))


def _emails_chauffeurs(dossiers: Sequence[Dossier]) -> dict[str, str | None]:
    try:
        comptes = SupabaseCompteRepository(SupabaseConfig.depuis_env())
        statuts = comptes.statuts([d.id for d in dossiers])
    except Exception:  # noqa: BLE001 — sans Supabase, on compare sans l'e-mail
        return {}
    return {str(d): invitation.email for d, invitation in statuts.items()}


def depots_postgres(engine: Engine) -> DepotsRapprochement:
    def prevenir(tenant_id: TenantId, nouveaux: list[AChoisir]) -> str:
        texte = (
            f"{len(nouveaux)} compte(s) Rollee attendent votre choix : ouvrez Entreprises, "
            "section « Comptes Rollee à relier »."
        )
        return prevenir_admins(engine, tenant_id, "AxeLCompta : comptes Rollee à relier", texte)

    return DepotsRapprochement(
        services=ServicesRollee(PostgresBranchements(engine), PostgresComptesRollee(engine)),
        liens=PostgresLiensRollee(engine),
        dossiers=PostgresDossierRepository(engine),
        sources=lambda tenant_id, dossiers: sources_reelles(engine, tenant_id, dossiers),
        prevenir=prevenir,
    )


def passer_tous(engine: Engine, ecrire: bool, maintenant: datetime) -> list[str]:
    """Rattrapage quotidien (tâches planifiées) : chaque portefeuille qui a Rollee."""
    depots = depots_postgres(engine)
    lignes: list[str] = []
    for tenant in depots.dossiers.lister_tenants():
        try:
            lignes += asyncio.run(passer_tenant(depots, tenant.id, ecrire, maintenant))
        except Exception as exc:  # noqa: BLE001 — un portefeuille en échec n'arrête pas les autres
            lignes.append(f"{tenant.id} : rapprochement en échec ({type(exc).__name__})")
    return lignes


async def rapprocher_inconnu(engine: Engine, tenant_id: TenantId, user_id: str) -> str:
    """Webhook d'un user Rollee qu'aucun dossier ne connaît : on le rapproche
    tout de suite, s'il n'est pas déjà dans la file. Écrit seulement si le
    rapprochement automatique est activé."""
    if not rapprochement_actif():
        return f"user {user_id} inconnu"
    depots = depots_postgres(engine)
    if any(a.rollee_user_id == user_id for a in depots.liens.a_choisir(tenant_id)):
        return f"user {user_id} inconnu, déjà à choisir"
    lignes = await passer_tenant(depots, tenant_id, True, datetime.now(UTC), seulement=user_id)
    return " ; ".join(lignes) or f"user {user_id} inconnu"
