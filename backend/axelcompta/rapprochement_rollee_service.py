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
import logging
import os
import time
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from axelcompta.comptes import SupabaseCompteRepository, SupabaseConfig
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.cartes_rollee import CartesRollee, CartesRolleeMemoire
from axelcompta.ingestion.cartes_rollee_postgres import PostgresCartesRollee
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
from axelcompta.tenants.branchements import a_interroger
from axelcompta.tenants.branchements_postgres import PostgresBranchements
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository

VARIABLE_ACTIF = "AXELCOMPTA_ROLLEE_RAPPROCHEMENT"
_journal = logging.getLogger("uvicorn.error")
# Phrase en cours, par dossier, lue par le bouton pendant la synchronisation.
_avancement: dict[str, str] = {}


def rapprochement_actif() -> bool:
    return os.environ.get(VARIABLE_ACTIF) == "1"


def cle_empreintes() -> bytes:
    """Dérivée de la clé des intégrations : sans elle, les empreintes ne se
    recalculent pas, même en volant la base."""
    cle = os.environ.get("AXELCOMPTA_CLE_INTEGRATIONS")
    if not cle:
        raise RuntimeError("AXELCOMPTA_CLE_INTEGRATIONS manquante : rien n'est comparé")
    return hashlib.sha256(b"rapprochement-rollee:" + cle.encode()).digest()


def retenir_avancement(dossier_id: str) -> Callable[[str], None]:
    """La phrase affichée sous le bouton, remplacée au fil de la lecture."""

    def noter(phrase: str) -> None:
        _avancement[dossier_id] = phrase

    return noter


def avancement_dossier(dossier_id: str) -> str | None:
    return _avancement.get(dossier_id)


def phrase_carte(nom: str, connus: int, faits: int, manquants: int, secondes: float) -> str:
    """La partie déjà en carte est comparée ; seuls les nouveaux se lisent."""
    if manquants == 0:
        return f"{nom} : {connus} comptes déjà connus."
    if faits <= 0:
        return f"{nom} : {connus} comptes déjà connus, {manquants} nouveaux à lire."
    if faits >= manquants:
        return f"{nom} : {connus} comptes déjà connus, {manquants} nouveaux lus."
    rythme = faits / secondes if secondes > 0 else 0.0
    reste = int((manquants - faits) / rythme) if rythme else 0
    return (
        f"{nom} : {connus} déjà connus, {faits}/{manquants} nouveaux lus, "
        f"environ {_duree_restante(reste)}."
    )


def phrase_lecture(nom: str, faits: int, total: int, secondes: float) -> str:
    """Où en est la lecture d'un compte Rollee, avec le temps qui reste."""
    if total == 0:
        return f"{nom} : aucun compte Rollee à lire."
    if faits <= 0:
        return f"{nom} : {total} comptes Rollee à lire."
    if faits >= total:
        return f"{nom} : {total} comptes Rollee lus."
    rythme = faits / secondes if secondes > 0 else 0.0
    reste = int((total - faits) / rythme) if rythme else 0
    return f"{nom} : {faits}/{total} comptes Rollee lus, environ {_duree_restante(reste)}."


def _duree_restante(secondes: int) -> str:
    if secondes < 60:
        return f"{max(secondes, 1)} s"
    return f"{(secondes + 30) // 60} min"


async def _avec(limite: asyncio.Semaphore | None, appel: Awaitable[Any]) -> Any:
    if limite is None:
        return await appel
    async with limite:
        return await appel


async def _infos_compte(
    client: RolleeHttpClient, compte_id: str, limite: asyncio.Semaphore | None
) -> tuple[dict[str, Any], str]:
    """Profil et IBAN d'un compte de plateforme. Un compte illisible ne bloque pas.
    Les deux appels partent ensemble : un 400 Uber n'attend pas la fin du profil."""

    async def profil() -> dict[str, Any]:
        try:
            lu = await _avec(limite, client.profil(compte_id))
        except Exception:  # noqa: BLE001 — Uber ou Bolt sans profil : on compare le reste
            return {}
        return lu if isinstance(lu, dict) else {}

    async def iban() -> str:
        try:
            lu = await _avec(limite, client.coordonnees_bancaires(compte_id))
        except Exception:  # noqa: BLE001
            return ""
        return str(lu.get("iban") or "") if isinstance(lu, dict) else ""

    lu_profil, lu_iban = await asyncio.gather(profil(), iban())
    return lu_profil, lu_iban


async def lire_user(
    client: RolleeHttpClient,
    brut: Mapping[str, Any],
    cle: bytes,
    limite: asyncio.Semaphore | None = None,
) -> UserRollee:
    """Un user Rollee, ses comptes de plateformes, réduits en empreintes."""
    user_id = str(brut["id"])
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    ibans, noms, emails, telephones, plateformes = [], [], [], [], []
    premier: tuple[str | None, str | None] = (None, None)
    for compte in await _avec(limite, client.comptes(user_id)):
        plateformes.append(str(compte.get("name") or compte.get("type") or "plateforme"))
        profil, iban = await _infos_compte(client, str(compte["id"]), limite)
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
# simultanés, Rollee répond 429 en 20 s (mesuré le 14/11). 5 à la fois :
# un 429 est journalisé et réessayé par le client.
APPELS_SIMULTANES = 5
# Chaque heure, le parc est complété par tranches : le passage reste court,
# le suivant reprend les comptes encore absents de la carte.
NOUVEAUX_PAR_PASSAGE = 120


def _avec_metadata(user: UserRollee, brut: Mapping[str, Any]) -> UserRollee:
    """Le dossier inscrit sur la liste Rollee, sans relire le profil."""
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    if not dossier:
        return user
    meta = str(dossier)
    return user if user.dossier_metadata == meta else replace(user, dossier_metadata=meta)


async def lire_users(
    client: RolleeHttpClient,
    cle: bytes,
    seulement: str | None = None,
    *,
    nom: str = "Rollee",
    noter: Callable[[str], None] | None = None,
    sauf: Collection[str] = (),
    connus: Mapping[str, UserRollee] | None = None,
    garder: Callable[[UserRollee], None] | None = None,
    avant_nouveaux: Callable[[Sequence[UserRollee]], None] | None = None,
    plafond: int | None = None,
    laisses: list[int] | None = None,
) -> list[UserRollee]:
    """Lit les users d'un compte Rollee. `sauf` : déjà reliés, rien à relire.

    `connus` : la carte déjà lue. Ces users sont comparés tout de suite,
    sans profil ni IBAN. `avant_nouveaux` reçoit cette partie avant que les
    users absents de la carte soient lus, en parallèle. `garder` enregistre
    chaque user nouvellement lu.
    """
    _publier(noter, f"{nom} : lecture de la liste…")
    deja = set(sauf)
    carte = dict(connus or {})
    bruts = [
        brut
        for brut in await client.utilisateurs()
        if "id" in brut
        and (seulement is None or str(brut["id"]) == seulement)
        and str(brut["id"]) not in deja
    ]
    reutilises = [
        _avec_metadata(carte[str(brut["id"])], brut) for brut in bruts if str(brut["id"]) in carte
    ]
    a_lire = [brut for brut in bruts if str(brut["id"]) not in carte]
    if plafond is not None and len(a_lire) > plafond:
        if laisses is not None:
            laisses.append(len(a_lire) - plafond)
        a_lire = a_lire[:plafond]
    elif laisses is not None:
        laisses.append(0)
    if reutilises and avant_nouveaux is not None:
        avant_nouveaux(reutilises)
    total = len(a_lire)
    if reutilises:
        _publier(noter, phrase_carte(nom, len(reutilises), 0, total, 0))
    else:
        _publier(noter, phrase_lecture(nom, 0, total, 0))
    if total == 0:
        return reutilises
    limite = asyncio.Semaphore(APPELS_SIMULTANES)
    faits = 0
    dernier = 0.0
    debut = time.monotonic()

    async def un(brut: Mapping[str, Any]) -> UserRollee:
        nonlocal faits, dernier
        user = await lire_user(client, brut, cle, limite)
        if garder is not None:
            garder(user)
        faits += 1
        maintenant = time.monotonic()
        if faits == 1 or faits == total or maintenant - dernier >= 5:
            dernier = maintenant
            phrase = (
                phrase_carte(nom, len(reutilises), faits, total, maintenant - debut)
                if reutilises
                else phrase_lecture(nom, faits, total, maintenant - debut)
            )
            _publier(noter, phrase)
        return user

    nouveaux = list(await asyncio.gather(*(un(brut) for brut in a_lire)))
    par_id = {user.user_id: user for user in (*reutilises, *nouveaux)}
    return [par_id[str(brut["id"])] for brut in bruts if str(brut["id"]) in par_id]


def _publier(noter: Callable[[str], None] | None, phrase: str) -> None:
    _journal.info("%s", phrase)
    if noter is not None:
        noter(phrase)


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


_CLES_TELEPHONE = ("phone", "mobile", "telephone", "cell", "phoneNumber", "mobilePhone")


def telephones_contact(contact: Mapping[str, Any] | None) -> list[str]:
    """Le contact Digifactory n'a pas un seul nom de champ pour le numéro."""
    if not contact:
        return []
    return [str(contact[cle]) for cle in _CLES_TELEPHONE if contact.get(cle)]


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
        empreintes(
            cle,
            sources.ibans.get(str(dossier.id), ()),
            noms,
            emails,
            telephones_contact(contact),
        ),
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


def _du_dossier(issues: Sequence[Issue], dossier_id: str) -> list[Issue]:
    """Ce qui concerne cette entreprise. Les users sans rapport restent
    dehors : un bouton sur une fiche ne réécrit pas toute la file."""
    return [issue for issue in issues if _concerne(issue, dossier_id)]


def _concerne(issue: Issue, dossier_id: str) -> bool:
    if issue.etat == "relie_auto":
        return issue.dossier_id == dossier_id
    if issue.etat == "a_choisir":
        return any(candidat.dossier_id == dossier_id for candidat in issue.candidats)
    return False


def phrase_rapprochement(issues: Sequence[Issue]) -> str:
    if any(issue.etat == "relie_auto" for issue in issues):
        return "Un seul compte Rollee correspond : le lien est posé."
    choix = sum(1 for issue in issues if issue.etat == "a_choisir")
    if choix == 1:
        return "Un compte Rollee correspond. Reliez-le sur cette fiche."
    if choix > 1:
        return f"{choix} comptes Rollee correspondent. Reliez le bon sur cette fiche."
    return "Aucun compte Rollee ne correspond à cette entreprise."


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
    cartes: CartesRollee = field(default_factory=CartesRolleeMemoire)


async def rapprocher_dossier(
    depots: DepotsRapprochement,
    dossier: Dossier,
    maintenant: datetime,
    noter: Callable[[str], None] | None = None,
) -> str:
    """Cherche le user Rollee de cette entreprise. Sans compte choisi sur la
    fiche, tous les comptes Rollee du portefeuille sont lus (« on interroge
    tous »). Un seul correspond : le lien est posé. Plusieurs : la file."""
    cle = cle_empreintes()
    dossiers = depots.dossiers.lister_par_tenant(dossier.tenant_id)
    sources = await depots.sources(dossier.tenant_id, dossiers)
    indices = [indices_dossier(d, sources, cle) for d in dossiers]
    liste = depots.services.branchements.lister(dossier.tenant_id)
    # La fiche n'a plus de menu : on lit tous les comptes Rollee du portefeuille.
    comptes = a_interroger(liste, TYPE_ROLLEE, None)
    if not comptes:
        return "Rollee n'est pas branché : ajoutez-le dans Intégrations."
    liens = depots.liens.liens(dossier.tenant_id)
    retires = depots.liens.paires_retirees(dossier.tenant_id)
    deja = frozenset(lien.rollee_user_id for lien in liens)
    trouves: list[Issue] = []
    a_signaler: list[AChoisir] = []
    decide = {"phrase": ""}

    def noter_fiche(phrase: str) -> None:
        if noter is None:
            return
        texte = f"{decide['phrase']} {phrase}" if decide["phrase"] else phrase
        noter(texte)

    for indice, branchement in enumerate(comptes, start=1):
        passage = Passage(dossier.tenant_id, branchement.id, maintenant, partiel=True)

        def integrer(users: Sequence[UserRollee], passage_courant: Passage = passage) -> None:
            poses = depots.liens.liens(dossier.tenant_id)
            lies = {lien.rollee_user_id for lien in poses}
            carte = depots.cartes.lire(dossier.tenant_id, passage_courant.branchement_id)
            deja_la = [
                connu
                for user_id, connu in carte.items()
                if user_id in lies and user_id not in {u.user_id for u in users}
            ]
            du_dossier = _du_dossier(
                trancher_tous([*deja_la, *users], indices, poses, retires), str(dossier.id)
            )
            if not du_dossier:
                return
            nouveaux = appliquer(depots.liens, du_dossier, users, passage_courant)
            a_signaler.extend(nouveaux)
            trouves.extend(du_dossier)
            decide["phrase"] = phrase_rapprochement(trouves)
            if noter is not None:
                noter(decide["phrase"])

        def garder(user: UserRollee, passage_courant: Passage = passage) -> None:
            depots.cartes.garder(
                dossier.tenant_id, passage_courant.branchement_id, user, maintenant
            )
            integrer([user], passage_courant)

        client = client_du_branchement(depots.services, branchement)
        try:
            await lire_users(
                client,
                cle,
                nom=f"{branchement.nom} ({indice}/{len(comptes)})",
                noter=noter_fiche,
                sauf=deja,
                connus=depots.cartes.lire(dossier.tenant_id, branchement.id),
                garder=garder,
                avant_nouveaux=integrer,
            )
        finally:
            await client.aclose()
    if a_signaler and depots.prevenir is not None:
        depots.prevenir(dossier.tenant_id, a_signaler)
    return phrase_rapprochement(trouves)


async def passer_tenant(
    depots: DepotsRapprochement,
    tenant_id: TenantId,
    ecrire: bool,
    maintenant: datetime,
    seulement: str | None = None,
    *,
    entretenir: bool = False,
    plafond: int | None = None,
) -> list[str]:
    """Un passage sur un portefeuille. `ecrire` faux : simulation, les liens
    ne sont pas posés. `entretenir` garde quand même chaque user lu dans la
    carte. `seulement` : un seul user (webhook). `plafond` : nombre de
    users absents de la carte lus dans ce passage."""
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
    liens_poses = depots.liens.liens(tenant_id)
    for branchement in rollee:

        def garder(user: UserRollee, branchement_id: str = branchement.id) -> None:
            depots.cartes.garder(tenant_id, branchement_id, user, maintenant)

        laisses: list[int] = []
        client = client_du_branchement(depots.services, branchement)
        try:
            users = await lire_users(
                client,
                cle,
                seulement,
                nom=branchement.nom,
                sauf=frozenset(lien.rollee_user_id for lien in liens_poses),
                connus=depots.cartes.lire(tenant_id, branchement.id),
                garder=garder if ecrire or entretenir else None,
                plafond=plafond,
                laisses=laisses,
            )
        finally:
            await client.aclose()
        issues = trancher_tous(users, indices, liens_poses, depots.liens.paires_retirees(tenant_id))
        if ecrire:
            mode = ""
        elif entretenir:
            mode = " (carte mise à jour, liens inchangés)"
        else:
            mode = " (simulation : rien n'est écrit)"
        encore = f", {laisses[-1]} encore absents de la carte" if laisses and laisses[-1] else ""
        lignes.append(f"{tenant_id} / {branchement.nom} : {resume(issues)}{mode}{encore}")
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
        cartes=PostgresCartesRollee(engine),
        sources=lambda tenant_id, dossiers: sources_reelles(engine, tenant_id, dossiers),
        prevenir=prevenir,
    )


def entretenir_cartes(engine: Engine, maintenant: datetime) -> list[str]:
    """Passage horaire : les comptes absents de la carte sont lus, par
    tranches. Un compte nouveau arrivé par webhook est lu tout de suite
    (`rapprocher_inconnu`). Les liens ne sont posés que si le rapprochement
    automatique est activé."""
    depots = depots_postgres(engine)
    ecrire = rapprochement_actif()
    lignes: list[str] = []
    for tenant in depots.dossiers.lister_tenants():
        try:
            lignes += asyncio.run(
                passer_tenant(
                    depots,
                    tenant.id,
                    ecrire,
                    maintenant,
                    entretenir=True,
                    plafond=NOUVEAUX_PAR_PASSAGE,
                )
            )
        except Exception as exc:  # noqa: BLE001 — un portefeuille en échec n'arrête pas les autres
            lignes.append(f"{tenant.id} : carte Rollee en échec ({type(exc).__name__})")
    return lignes


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
    """Webhook d'un user Rollee qu'aucun dossier ne connaît : il entre dans
    la carte tout de suite. Le lien n'est posé que si le rapprochement
    automatique est activé. Déjà dans la file : rien à relire."""
    depots = depots_postgres(engine)
    if any(a.rollee_user_id == user_id for a in depots.liens.a_choisir(tenant_id)):
        return f"user {user_id} inconnu, déjà à choisir"
    lignes = await passer_tenant(
        depots,
        tenant_id,
        rapprochement_actif(),
        datetime.now(UTC),
        seulement=user_id,
        entretenir=True,
    )
    return " ; ".join(lignes) or f"user {user_id} inconnu"
