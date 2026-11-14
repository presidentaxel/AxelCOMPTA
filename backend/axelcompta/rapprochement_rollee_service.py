"""Relier les users Rollee existants à leurs dossiers (AXE-911).

Composition root : lit la liste des users, puis les profils des comptes
encore inconnus. Les empreintes servent au rapprochement. La carte garde
le nom en clair et l'e-mail masqué pour la recherche du gestionnaire,
jamais un montant ni un IBAN en clair.

Deux modes :

* simulation (par défaut) : le bilan, sans rien écrire ;
* application : les liens sûrs sont posés (`auto`, avec l'indice). Un nom
  partagé ou un signal ambigu va dans la file « à choisir ». Un user sans
  correspondance n'y va pas.

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
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.engine import Engine

from axelcompta.comptes import SupabaseCompteRepository, SupabaseConfig
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.annuaire_rollee import masquer_email
from axelcompta.ingestion.cartes_rollee import CartesRollee, CartesRolleeMemoire
from axelcompta.ingestion.cartes_rollee_postgres import PostgresCartesRollee
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


def _erreur_du_compte(exc: RolleeIndisponible) -> bool:
    """Une 5xx répétée sur un compte précis, pas Rollee débordé (429)."""
    return exc.statut is not None and exc.statut >= 500


async def _profil_compte(
    client: RolleeHttpClient,
    compte_id: str,
    limite: asyncio.Semaphore | None,
    tolerer: bool,
) -> dict[str, Any]:
    """Le profil seulement. L'IBAN n'est plus demandé : Uber répond 400, Bolt
    une liste vide, et aucun IBAN n'a correspondu (mesuré le 14/11)."""
    try:
        lu = await _avec(limite, client.profil(compte_id))
    except RolleeIndisponible as exc:
        if not (tolerer and _erreur_du_compte(exc)):
            raise
        return {}
    except RolleeAuthError:
        raise
    except Exception:  # noqa: BLE001 — Uber ou Bolt sans profil : on compare le reste
        return {}
    return lu if isinstance(lu, dict) else {}


async def lire_user(
    client: RolleeHttpClient,
    brut: Mapping[str, Any],
    cle: bytes,
    limite: asyncio.Semaphore | None = None,
    tolerer: bool = False,
) -> UserRollee:
    """Un user Rollee et ses profils de plateforme, réduits en empreintes.
    Le nom en clair et l'e-mail masqué restent pour la recherche."""
    user_id = str(brut["id"])
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    noms, emails, telephones, plateformes = [], [], [], []
    premier: tuple[str | None, str | None] = (None, None)
    email_vu: str | None = None
    for compte in await _avec(limite, client.comptes(user_id)):
        plateformes.append(str(compte.get("name") or compte.get("type") or "plateforme"))
        profil = await _profil_compte(client, str(compte["id"]), limite, tolerer)
        prenom, nom = profil.get("first_name"), profil.get("last_name")
        if prenom or nom:
            noms.append(normaliser_nom(prenom, nom))
            premier = premier if premier != (None, None) else (prenom, nom)
        if email_vu is None and isinstance(profil.get("email"), str):
            email_vu = profil.get("email")
        emails.append(profil.get("email"))
        telephones.append(profil.get("phone"))
    return UserRollee(
        user_id,
        str(dossier) if dossier else None,
        empreintes(cle, (), noms, emails, telephones),
        apercu(premier[0], premier[1], plateformes, None, masquer_email(email_vu)),
        _nombre_comptes(brut),
    )


# À 5 ou 8 appels simultanés, Rollee répond 429 (mesuré le 14/11). Le débit
# plafonne vers 7 appels/s : 3 à la fois.
APPELS_SIMULTANES = 3
# Chaque heure, le parc est complété par tranches : le passage reste court,
# le suivant reprend les comptes encore absents de la carte.
NOUVEAUX_PAR_PASSAGE = 120


def _nombre_comptes(brut: Mapping[str, Any]) -> int | None:
    valeur = brut.get("accounts_number")
    return valeur if isinstance(valeur, int) else None


def _user_vide(brut: Mapping[str, Any]) -> UserRollee:
    """Aucune plateforme : on le garde sans appeler /accounts ni le profil."""
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    return UserRollee(
        str(brut["id"]), str(dossier) if dossier else None, Empreintes(), accounts_number=0
    )


def _classe(brut: Mapping[str, Any], carte: Mapping[str, UserRollee], sauf: set[str]) -> str:
    """`vide` : rien à interroger. `connu` : la carte suffit. `hors` : déjà
    relié et inchangé. `lire` : absent, ou `accounts_number` a changé."""
    if _nombre_comptes(brut) == 0:
        return "vide"
    connu = carte.get(str(brut["id"]))
    change = connu is not None and connu.accounts_number != _nombre_comptes(brut)
    if str(brut["id"]) in sauf and not change:
        return "hors"
    if connu is not None and not change:
        return "connu"
    return "lire"


@dataclass(frozen=True, slots=True)
class Lecture:
    """Les users lus, ceux que Rollee n'a pas rendus, et ceux laissés pour plus tard."""

    users: list[UserRollee]
    erreurs: tuple[str, ...] = ()
    profils_en_erreur: tuple[str, ...] = ()
    laisses: int = 0

    @property
    def illisibles(self) -> int:
        return len(self.erreurs)


@dataclass(frozen=True, slots=True)
class BilanDossier:
    phrase: str
    a_lire: int = 0
    lien_pose: bool = False


def _avec_metadata(user: UserRollee, brut: Mapping[str, Any]) -> UserRollee:
    """Le dossier inscrit sur la liste Rollee, sans relire le profil."""
    metadata = brut.get("metadata") or {}
    dossier = metadata.get("dossier_id") if isinstance(metadata, Mapping) else None
    if not dossier:
        return user
    meta = str(dossier)
    return user if user.dossier_metadata == meta else replace(user, dossier_metadata=meta)


def _noter_lot(
    noter: Callable[[str], None] | None,
    nom: str,
    connus: int,
    faits: int,
    total: int,
    debut: float,
    dernier: float,
) -> float:
    maintenant = time.monotonic()
    if faits not in (1, total) and maintenant - dernier < 5:
        return dernier
    phrase = (
        phrase_carte(nom, connus, faits, total, maintenant - debut)
        if connus
        else phrase_lecture(nom, faits, total, maintenant - debut)
    )
    _publier(noter, phrase)
    return maintenant


async def _lire_les_absents(
    client: RolleeHttpClient,
    a_lire: Sequence[Mapping[str, Any]],
    cle: bytes,
    nom: str,
    noter: Callable[[str], None] | None,
    connus: int,
    garder: Callable[[UserRollee], None] | None,
) -> tuple[list[UserRollee], list[str], list[str]]:
    """Lit les users manquants, puis relit un par un ceux qu'un 429 a fait rater."""
    limite = asyncio.Semaphore(APPELS_SIMULTANES)
    faits = 0
    dernier = 0.0
    debut = time.monotonic()
    total = len(a_lire)

    async def un(brut: Mapping[str, Any]) -> UserRollee | None:
        nonlocal faits, dernier
        try:
            user = await lire_user(client, brut, cle, limite)
        except RolleeIndisponible:
            return None
        if garder is not None:
            garder(user)
        faits += 1
        dernier = _noter_lot(noter, nom, connus, faits, total, debut, dernier)
        return user

    lus = list(await asyncio.gather(*(un(brut) for brut in a_lire)))
    users = [user for user in lus if user is not None]
    erreurs, profils = await _relire_les_rates(client, a_lire, lus, cle, garder, users)
    if faits != total and users:
        _noter_lot(noter, nom, connus, len(users), total, debut, 0)
    return users, erreurs, profils


async def _relire_les_rates(
    client: RolleeHttpClient,
    a_lire: Sequence[Mapping[str, Any]],
    lus: Sequence[UserRollee | None],
    cle: bytes,
    garder: Callable[[UserRollee], None] | None,
    users: list[UserRollee],
) -> tuple[list[str], list[str]]:
    erreurs: list[str] = []
    profils: list[str] = []
    for brut, lu in zip(a_lire, lus, strict=True):
        if lu is not None:
            continue
        user, erreur, profil = await _relire_un(client, brut, cle)
        if user is not None:
            users.append(user)
            if garder is not None:
                garder(user)
        if erreur:
            erreurs.append(erreur)
        if profil:
            profils.append(profil)
    return erreurs, profils


async def _relire_un(
    client: RolleeHttpClient, brut: Mapping[str, Any], cle: bytes
) -> tuple[UserRollee | None, str | None, str | None]:
    try:
        return await lire_user(client, brut, cle, None), None, None
    except RolleeIndisponible as exc:
        if not _erreur_du_compte(exc):
            return None, str(exc), None
        try:
            return await lire_user(client, brut, cle, None, tolerer=True), None, str(exc)
        except RolleeIndisponible as encore:
            return None, str(encore), None


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
    lire_absents: bool = True,
) -> Lecture:
    """Liste GET /users, puis la carte. Un user à 0 plateforme n'est pas
    interrogé. Un user de la carte n'est relu que si `accounts_number` change.
    `lire_absents` faux : on compte les absents, on ne les appelle pas."""
    _publier(noter, f"{nom} : lecture de la liste…")
    carte = dict(connus or {})
    bruts = [
        brut
        for brut in await client.utilisateurs()
        if "id" in brut and (seulement is None or str(brut["id"]) == seulement)
    ]
    vides, reutilises, a_lire = _repartir(bruts, carte, set(sauf))
    if garder is not None:
        for user in vides:
            garder(user)
    laisses_n, a_lire = _plafonner(a_lire, plafond, lire_absents)
    if laisses is not None:
        laisses.append(laisses_n)
    prets = [*vides, *reutilises]
    if prets and avant_nouveaux is not None:
        avant_nouveaux(prets)
    _annoncer(noter, nom, len(reutilises), len(a_lire))
    if not a_lire:
        return Lecture(prets, laisses=laisses_n)
    nouveaux, erreurs, profils = await _lire_les_absents(
        client, a_lire, cle, nom, noter, len(reutilises), garder
    )
    par_id = {user.user_id: user for user in (*prets, *nouveaux)}
    return Lecture(
        [par_id[str(brut["id"])] for brut in bruts if str(brut["id"]) in par_id],
        tuple(erreurs),
        tuple(profils),
        laisses_n,
    )


def _repartir(
    bruts: Sequence[Mapping[str, Any]], carte: Mapping[str, UserRollee], sauf: set[str]
) -> tuple[list[UserRollee], list[UserRollee], list[Mapping[str, Any]]]:
    vides: list[UserRollee] = []
    reutilises: list[UserRollee] = []
    a_lire: list[Mapping[str, Any]] = []
    for brut in bruts:
        sorte = _classe(brut, carte, sauf)
        if sorte == "vide":
            vides.append(_user_vide(brut))
        elif sorte == "connu":
            reutilises.append(_avec_metadata(carte[str(brut["id"])], brut))
        elif sorte == "lire":
            a_lire.append(brut)
    return vides, reutilises, a_lire


def _plafonner(
    a_lire: list[Mapping[str, Any]], plafond: int | None, lire_absents: bool
) -> tuple[int, list[Mapping[str, Any]]]:
    if not lire_absents:
        return len(a_lire), []
    if plafond is not None and len(a_lire) > plafond:
        return len(a_lire) - plafond, a_lire[:plafond]
    return 0, a_lire


def _annoncer(noter: Callable[[str], None] | None, nom: str, connus: int, total: int) -> None:
    if connus:
        _publier(noter, phrase_carte(nom, connus, 0, total, 0))
    elif total:
        _publier(noter, phrase_lecture(nom, 0, total, 0))


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
        if issue.etat == "non_trouve":
            # Comptes Rollee partagés avec d'autres cabinets : un user sans
            # candidat n'entre pas dans la file du gestionnaire.
            continue
        etat = "a_choisir"
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
    cartes: CartesRollee = field(default_factory=CartesRolleeMemoire)


async def rapprocher_dossier(
    depots: DepotsRapprochement,
    dossier: Dossier,
    maintenant: datetime,
    noter: Callable[[str], None] | None = None,
    lire_absents: bool = True,
) -> BilanDossier:
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
        return BilanDossier("Rollee n'est pas branché : ajoutez-le dans Intégrations.")
    liens = depots.liens.liens(dossier.tenant_id)
    retires = depots.liens.paires_retirees(dossier.tenant_id)
    deja = frozenset(lien.rollee_user_id for lien in liens)
    lectures: list[tuple[Passage, Lecture]] = []
    for indice, branchement in enumerate(comptes, start=1):
        passage = Passage(dossier.tenant_id, branchement.id, maintenant, partiel=True)

        def garder(user: UserRollee, passage_courant: Passage = passage) -> None:
            depots.cartes.garder(
                dossier.tenant_id, passage_courant.branchement_id, user, maintenant
            )

        client = client_du_branchement(depots.services, branchement)
        try:
            lecture = await lire_users(
                client,
                cle,
                nom=f"{branchement.nom} ({indice}/{len(comptes)})",
                noter=noter,
                sauf=deja,
                connus=depots.cartes.lire(dossier.tenant_id, branchement.id),
                garder=garder,
                lire_absents=lire_absents,
            )
        finally:
            await client.aclose()
        lectures.append((passage, lecture))
    return _conclure_dossier(depots, dossier, indices, liens, retires, lectures)


def _conclure_dossier(
    depots: DepotsRapprochement,
    dossier: Dossier,
    indices: Sequence[DossierIndices],
    liens: Sequence[Lien],
    retires: frozenset[tuple[str, str]],
    lectures: Sequence[tuple[Passage, Lecture]],
) -> BilanDossier:
    """Une seule décision, tous comptes Rollee confondus, pour le nom unique."""
    deja = {lien.rollee_user_id for lien in liens}
    users: list[UserRollee] = []
    for passage, lecture in lectures:
        carte = depots.cartes.lire(dossier.tenant_id, passage.branchement_id)
        users.extend(connu for user_id, connu in carte.items() if user_id in deja)
        users.extend(lecture.users)
    a_lire = sum(lecture.laisses for _, lecture in lectures)
    erreurs = sum(lecture.illisibles for _, lecture in lectures)
    issues = trancher_tous(users, indices, liens, retires, complet=a_lire == 0 and erreurs == 0)
    a_signaler: list[AChoisir] = []
    trouves: list[Issue] = []
    for passage, lecture in lectures:
        siens = {user.user_id for user in lecture.users}
        du_dossier = _du_dossier([i for i in issues if i.user_id in siens], str(dossier.id))
        a_signaler.extend(appliquer(depots.liens, du_dossier, lecture.users, passage))
        trouves.extend(du_dossier)
    if a_signaler and depots.prevenir is not None:
        depots.prevenir(dossier.tenant_id, a_signaler)
    return BilanDossier(
        phrase_rapprochement(trouves),
        a_lire,
        any(issue.etat == "relie_auto" for issue in trouves),
    )


async def _lire_portefeuille(
    depots: DepotsRapprochement,
    tenant_id: TenantId,
    cle: bytes,
    rollee: Sequence[Any],
    liens_poses: Sequence[Lien],
    memoriser: bool,
    maintenant: datetime,
    seulement: str | None,
    plafond: int | None,
) -> list[tuple[Any, Lecture]]:
    deja = frozenset(lien.rollee_user_id for lien in liens_poses)
    lus: list[tuple[Any, Lecture]] = []
    for branchement in rollee:

        def garder(user: UserRollee, branchement_id: str = branchement.id) -> None:
            depots.cartes.garder(tenant_id, branchement_id, user, maintenant)

        client = client_du_branchement(depots.services, branchement)
        try:
            lecture = await lire_users(
                client,
                cle,
                seulement,
                nom=branchement.nom,
                sauf=deja,
                connus=depots.cartes.lire(tenant_id, branchement.id),
                garder=garder if memoriser else None,
                plafond=plafond,
            )
        finally:
            await client.aclose()
        lus.append((branchement, lecture))
    return lus


def _bilan_portefeuille(
    depots: DepotsRapprochement,
    tenant_id: TenantId,
    indices: Sequence[DossierIndices],
    liens_poses: Sequence[Lien],
    lus: Sequence[tuple[Any, Lecture]],
    ecrire: bool,
    entretenir: bool,
    maintenant: datetime,
    seulement: str | None,
) -> list[str]:
    lies = {lien.rollee_user_id for lien in liens_poses}
    tous: list[UserRollee] = []
    for branchement, lecture in lus:
        carte = depots.cartes.lire(tenant_id, branchement.id)
        tous.extend(user for user_id, user in carte.items() if user_id in lies)
        tous.extend(lecture.users)
    incomplet = seulement is not None or any(
        lecture.illisibles or lecture.laisses for _, lecture in lus
    )
    issues = trancher_tous(
        tous, indices, liens_poses, depots.liens.paires_retirees(tenant_id), complet=not incomplet
    )
    lignes = _lignes_de_bilan(tenant_id, lus, issues, ecrire, entretenir)
    if not ecrire:
        return lignes
    return lignes + _poser_liens(depots, tenant_id, lus, issues, maintenant, incomplet)


def _lignes_de_bilan(
    tenant_id: TenantId,
    lus: Sequence[tuple[Any, Lecture]],
    issues: Sequence[Issue],
    ecrire: bool,
    entretenir: bool,
) -> list[str]:
    if ecrire:
        mode = ""
    elif entretenir:
        mode = " (carte mise à jour, liens inchangés)"
    else:
        mode = " (simulation : rien n'est écrit)"
    lignes = []
    for branchement, lecture in lus:
        siens = {user.user_id for user in lecture.users}
        encore = f", {lecture.laisses} encore absents de la carte" if lecture.laisses else ""
        du_compte = [issue for issue in issues if issue.user_id in siens]
        lignes.append(f"{tenant_id} / {branchement.nom} : {resume(du_compte)}{mode}{encore}")
    erreurs = [erreur for _, lecture in lus for erreur in lecture.erreurs]
    if erreurs:
        lignes.append(
            f"  {len(erreurs)} user(s) Rollee illisible(s) : "
            "aucun lien par le nom seul à ce passage"
        )
    profils = [profil for _, lecture in lus for profil in lecture.profils_en_erreur]
    if profils:
        lignes.append(
            f"  {len(profils)} profil(s) toujours en erreur chez Rollee, comptés sans nom"
        )
    return lignes


def _poser_liens(
    depots: DepotsRapprochement,
    tenant_id: TenantId,
    lus: Sequence[tuple[Any, Lecture]],
    issues: Sequence[Issue],
    maintenant: datetime,
    incomplet: bool,
) -> list[str]:
    lignes = []
    for branchement, lecture in lus:
        siens = {user.user_id for user in lecture.users}
        du_compte = [issue for issue in issues if issue.user_id in siens]
        passage = Passage(tenant_id, branchement.id, maintenant, incomplet)
        nouveaux = appliquer(depots.liens, du_compte, lecture.users, passage)
        if nouveaux and depots.prevenir is not None:
            lignes.append(f"{tenant_id} : {depots.prevenir(tenant_id, nouveaux)}")
    return lignes


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
    liens_poses = depots.liens.liens(tenant_id)
    lus = await _lire_portefeuille(
        depots,
        tenant_id,
        cle,
        rollee,
        liens_poses,
        ecrire or entretenir,
        maintenant,
        seulement,
        plafond,
    )
    return _bilan_portefeuille(
        depots, tenant_id, indices, liens_poses, lus, ecrire, entretenir, maintenant, seulement
    )


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


def rapprocher_maintenant(
    engine: Engine, tenant_id: TenantId, dossier_id: str | None = None
) -> str:
    """Job du worker : remplit la carte sans plafond, tranche, puis lit les
    revenus des dossiers qui viennent d'être reliés (et de celui demandé)."""
    depots = depots_postgres(engine)
    avant = {lien.rollee_user_id for lien in depots.liens.liens(tenant_id)}
    lignes = asyncio.run(passer_tenant(depots, tenant_id, True, datetime.now(UTC)))
    apres = depots.liens.liens(tenant_id)
    cibles = {str(lien.dossier_id) for lien in apres if lien.rollee_user_id not in avant}
    if dossier_id and any(str(lien.dossier_id) == dossier_id for lien in apres):
        cibles.add(dossier_id)
    for ident in sorted(cibles):
        lignes.append(_relever_un_dossier(engine, ident))
    return " · ".join(ligne.strip() for ligne in lignes) or "aucun compte Rollee actif"


def _relever_un_dossier(engine: Engine, dossier_id: str) -> str:
    from axelcompta.plateformes_rollee import synchroniser_dossier
    from axelcompta.revenus_rollee import depots_postgres as depots_revenus
    from axelcompta.revenus_rollee import relever_revenus

    dossier = PostgresDossierRepository(engine).obtenir(DossierId(dossier_id))
    if dossier is None:
        return f"{dossier_id} : dossier introuvable"
    services = ServicesRollee(PostgresBranchements(engine), PostgresComptesRollee(engine))
    plateformes = asyncio.run(synchroniser_dossier(services, dossier))
    revenus = asyncio.run(relever_revenus(services, depots_revenus(engine), dossier, date.today()))
    return f"{plateformes} {revenus}".strip()
