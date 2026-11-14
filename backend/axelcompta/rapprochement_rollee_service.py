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
from axelcompta.ingestion.providers.rollee import (
    RolleeAuthError,
    RolleeHttpClient,
    RolleeIndisponible,
)
from axelcompta.ingestion.rapprochement_rollee import (
    DossierIndices,
    Empreintes,
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
from axelcompta.tenants.branchements import Branchement
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


def _sans_iban(compte: Mapping[str, Any]) -> bool:
    """Uber répond toujours 400 sur l'IBAN (mesuré le 14/11) : ne pas le
    demander épargne la limite de débit de Rollee."""
    return "uber" in str(compte.get("name") or compte.get("type") or "").lower()


def _erreur_du_compte(exc: RolleeIndisponible) -> bool:
    """Une 5xx répétée sur un compte précis (mesuré le 14/11 : 3 profils
    toujours en 500), pas Rollee débordé (429)."""
    return exc.statut is not None and exc.statut >= 500


async def _infos_compte(
    client: RolleeHttpClient, compte_id: str, avec_iban: bool = True, tolerer: bool = False
) -> tuple[dict[str, Any], str]:
    """Profil et IBAN d'un compte de plateforme. Un refus de Rollee (Uber
    répond 400 sur l'IBAN) laisse l'indice vide. Rollee débordé ou jeton
    refusé, non : le user est illisible (AXE-918), jamais pris pour un user
    sans nom, sinon un homonyme passerait pour unique. `tolerer` : à la
    relecture finale, un profil toujours en 5xx est compté sans nom."""
    try:
        profil = await client.profil(compte_id)
    except RolleeIndisponible as exc:
        if not (tolerer and _erreur_du_compte(exc)):
            raise
        profil = {}
    except RolleeAuthError:
        raise
    except Exception:  # noqa: BLE001 — Uber ou Bolt sans profil : on compare le reste
        profil = {}
    if not avec_iban:
        return profil, ""
    try:
        iban = str((await client.coordonnees_bancaires(compte_id)).get("iban") or "")
    except RolleeIndisponible as exc:
        if not (tolerer and _erreur_du_compte(exc)):
            raise
        iban = ""
    except RolleeAuthError:
        raise
    except Exception:  # noqa: BLE001
        iban = ""
    return profil, iban


async def lire_user(
    client: RolleeHttpClient, brut: Mapping[str, Any], cle: bytes, tolerer: bool = False
) -> UserRollee:
    """Un user Rollee, ses comptes de plateformes, réduits en empreintes."""
    user_id = str(brut["id"])
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    ibans, noms, emails, telephones, plateformes = [], [], [], [], []
    premier: tuple[str | None, str | None] = (None, None)
    for compte in await client.comptes(user_id):
        plateformes.append(str(compte.get("name") or compte.get("type") or "plateforme"))
        profil, iban = await _infos_compte(
            client, str(compte["id"]), not _sans_iban(compte), tolerer
        )
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


# AXE-917 : un passage lit ~2 200 users (comptes, profil, IBAN). À 8 appels
# simultanés, Rollee répond 429 en 20 s (mesuré le 14/11) : 3 à la fois.
APPELS_SIMULTANES = 3


@dataclass(frozen=True, slots=True)
class Lecture:
    """Les users lus d'un compte Rollee, et ceux que Rollee n'a pas rendus."""

    users: list[UserRollee]
    erreurs: tuple[str, ...] = ()  # « GET /users/<id>/accounts : 429 après 5 essais »
    # Users lus, mais dont un profil reste en 5xx chez Rollee : comptés sans
    # nom, signalés dans le bilan, sans bloquer le lien par le nom.
    profils_en_erreur: tuple[str, ...] = ()

    @property
    def illisibles(self) -> int:
        return len(self.erreurs)


def _sans_plateforme(brut: Mapping[str, Any]) -> UserRollee | None:
    """`accounts_number` à 0 dans la liste des users : aucune plateforme, donc
    aucun nom à lire. On ne l'interroge pas (plus de la moitié des users,
    autant d'appels épargnés à la limite de débit de Rollee)."""
    if brut.get("accounts_number") != 0:
        return None
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    return UserRollee(str(brut["id"]), str(dossier) if dossier else None, Empreintes())


async def lire_users(client: RolleeHttpClient, cle: bytes, seulement: str | None = None) -> Lecture:
    bruts = [
        brut
        for brut in await client.utilisateurs()
        if "id" in brut and (seulement is None or str(brut["id"]) == seulement)
    ]
    limite = asyncio.Semaphore(APPELS_SIMULTANES)

    async def un(brut: Mapping[str, Any]) -> UserRollee | None:
        if (vide := _sans_plateforme(brut)) is not None:
            return vide
        async with limite:
            try:
                return await lire_user(client, brut, cle)
            except RolleeIndisponible:
                return None

    lus = await asyncio.gather(*(un(brut) for brut in bruts))
    users = [u for u in lus if u is not None]
    # Rollee débordé sur quelques users : on les relit un par un, à la fin.
    erreurs: list[str] = []
    profils: list[str] = []
    for brut, lu in zip(bruts, lus, strict=True):
        if lu is not None:
            continue
        try:
            users.append(await lire_user(client, brut, cle))
        except RolleeIndisponible as exc:
            if not _erreur_du_compte(exc):
                erreurs.append(str(exc))
                continue
            try:
                users.append(await lire_user(client, brut, cle, tolerer=True))
                profils.append(str(exc))
            except RolleeIndisponible as encore:
                erreurs.append(str(encore))
    return Lecture(users, tuple(erreurs), tuple(profils))


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
        if issue.etat == "non_trouve":
            # AXE-918 : les comptes Rollee sont partagés avec d'autres
            # cabinets (plus de 2 000 users pour 14 dossiers) ; un user sans
            # candidat n'est pas à montrer au gestionnaire.
            continue
        attente.append(
            AChoisir(
                issue.user_id,
                passage.tenant_id,
                passage.branchement_id,
                "a_choisir",
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
    complet: bool = True,
) -> list[Issue]:
    poses = {x.rollee_user_id: str(x.dossier_id) for x in liens}
    return rapprocher(users, dossiers, poses, retires, complet)


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
    n'est écrit. `seulement` : un seul user (webhook d'un user inconnu).

    AXE-918 : les users de **tous** les comptes Rollee sont lus avant de
    trancher, une seule fois : un nom n'est « unique » que sur l'ensemble, et
    deux users de deux comptes qui visent le même dossier vont au
    gestionnaire. Le lien est ensuite posé sur le compte du user."""
    cle = cle_empreintes()
    dossiers = depots.dossiers.lister_par_tenant(tenant_id)
    sources = await depots.sources(tenant_id, dossiers)
    indices = [indices_dossier(d, sources, cle) for d in dossiers]
    par_branchement = await _users_par_branchement(depots, tenant_id, cle, seulement)
    tous = [u for _b, lecture in par_branchement for u in lecture.users]
    erreurs = [e for _b, lecture in par_branchement for e in lecture.erreurs]
    illisibles = len(erreurs)
    issues = trancher_tous(
        tous,
        indices,
        depots.liens.liens(tenant_id),
        depots.liens.paires_retirees(tenant_id),
        # Un user illisible pourrait porter le même nom : pas de lien par le
        # nom seul tant que la liste n'est pas complète.
        complet=seulement is None and illisibles == 0,
    )
    mode = "" if ecrire else " (simulation : rien n'est écrit)"
    lignes = [f"{tenant_id} : {resume(issues)}{mode}"]
    if illisibles:
        lignes.append(
            f"  {illisibles} user(s) Rollee illisible(s) (Rollee débordé) : "
            "aucun lien par le nom seul à ce passage, relancez plus tard"
        )
        lignes += [f"    {erreur}" for erreur in erreurs[:5]]
    profils = [p for _b, lecture in par_branchement for p in lecture.profils_en_erreur]
    if profils:
        lignes.append(
            f"  {len(profils)} profil(s) toujours en erreur chez Rollee, comptés sans nom :"
        )
        lignes += [f"    {profil}" for profil in profils[:5]]
    nouveaux: list[AChoisir] = []
    for branchement, lecture in par_branchement:
        users = lecture.users
        siens = {u.user_id for u in users}
        issues_du_compte = [i for i in issues if i.user_id in siens]
        lignes.append(f"  {branchement.nom} : {resume(issues_du_compte)}")
        if ecrire:
            # Des users non relus gardent leur place dans la file.
            partiel = seulement is not None or lecture.illisibles > 0
            passage = Passage(tenant_id, branchement.id, maintenant, partiel)
            nouveaux += appliquer(depots.liens, issues_du_compte, users, passage)
    if nouveaux and depots.prevenir is not None:
        lignes.append(f"{tenant_id} : {depots.prevenir(tenant_id, nouveaux)}")
    return lignes


async def _users_par_branchement(
    depots: DepotsRapprochement, tenant_id: TenantId, cle: bytes, seulement: str | None
) -> list[tuple[Branchement, Lecture]]:
    lus = []
    for branchement in depots.services.branchements.lister(tenant_id):
        if branchement.type != TYPE_ROLLEE or not branchement.actif:
            continue
        client = client_du_branchement(depots.services, branchement)
        try:
            lus.append((branchement, await lire_users(client, cle, seulement)))
        finally:
            await client.aclose()
    return lus


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


def rapprocher_maintenant(engine: Engine, tenant_id: TenantId) -> str:
    """Bouton « Rapprocher Rollee » (AXE-918), exécuté par le worker : écrit,
    même sans `AXELCOMPTA_ROLLEE_RAPPROCHEMENT` (qui ne vise que la nuit)."""
    lignes = asyncio.run(passer_tenant(depots_postgres(engine), tenant_id, True, datetime.now(UTC)))
    return " · ".join(ligne.strip() for ligne in lignes) or "aucun compte Rollee actif"


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
