"""Le chauffeur relie ses plateformes via Rollee Connect (AXE-819).

Composition root (doc 18) : branchement Rollee du dossier (AXE-872), client
(AXE-818), comptes reliés (`ingestion.comptes_rollee`).

1. Le chauffeur demande à relier : le « user » Rollee du dossier est créé à
   ce moment-là (une fois), avec le seul `dossier_id` en métadonnée. Rollee
   renvoie un lien Rollee Connect valable 30 minutes.
2. Il relie Uber, Bolt… chez Rollee, avec ses propres identifiants (jamais
   vus par AxeLCompta).
3. Au retour, la liste des comptes est relue chez Rollee et gardée.

Le user Rollee appartient au compte Rollee du branchement qui l'a créé : il
reste lié à ce branchement, même si le défaut change ensuite.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol

from sqlalchemy.engine import Engine

from axelcompta.core.chiffrement import dechiffrer
from axelcompta.core.errors import Conflit
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.metriques import METRIQUES
from axelcompta.core.rls import contexte_identite
from axelcompta.ingestion.comptes_rollee import (
    CompteRelie,
    ComptesRolleeRepository,
    UtilisateurRollee,
    depuis_rollee,
    retenir_compte,
)
from axelcompta.ingestion.comptes_rollee_postgres import PostgresComptesRollee
from axelcompta.ingestion.providers.rollee import RolleeHttpClient, RolleeIndisponible
from axelcompta.ingestion.rapprochement_rollee import empreinte, nom_du_profil
from axelcompta.ingestion.webhooks_rollee import (
    TYPES_COMPTES,
    TYPES_DONNEES,
    EvenementIllisible,
    EvenementRollee,
    EvenementsRolleeRepository,
    lire,
    resume,
    signature_valide,
)
from axelcompta.ingestion.webhooks_rollee_postgres import PostgresEvenementsRollee
from axelcompta.jobs.file import TYPE_ROLLEE as JOB_ROLLEE
from axelcompta.jobs.postgres import FilePostgres
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementsRepository,
    garder_parametre,
    pour_dossier,
)
from axelcompta.tenants.branchements_postgres import PostgresBranchements, branchement_pour_webhook
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.postgres import PostgresDossierRepository
from axelcompta.tenants.repository import DossierRepository
from axelcompta.workflow.notifications import TYPE_PLATEFORME_A_RECONNECTER, NotificationEnvoyee
from axelcompta.workflow.notifications_postgres import PostgresNotificationRepository

TYPE_ROLLEE = "rollee"
FabriqueClient = Callable[[Branchement, Callable[[str], None]], RolleeHttpClient]


class RolleeNonBranche(Conflit):
    """Aucun branchement Rollee actif pour ce dossier."""


def _client_par_defaut(branchement: Branchement, garder: Callable[[str], None]) -> RolleeHttpClient:
    return RolleeHttpClient.depuis_parametres(branchement.parametres(), garder)


@dataclass
class ServicesRollee:
    branchements: BranchementsRepository
    comptes: ComptesRolleeRepository
    fabrique: FabriqueClient = _client_par_defaut
    maintenant: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Session:
    lien: str
    expire_le: str | None


def branchement_du_dossier(services: ServicesRollee, dossier: Dossier) -> Branchement:
    """Celui qui a créé le user Rollee du dossier, sinon le choix du dossier.
    Sans choix : le seul accès actif. Rollee n'a pas de défaut."""
    utilisateur = services.comptes.utilisateur(dossier.id)
    if utilisateur is not None:
        actifs = services.branchements.lister(dossier.tenant_id)
        lie = next((b for b in actifs if b.id == utilisateur.branchement_id and b.actif), None)
        if lie is None:
            raise RolleeNonBranche(
                "Le branchement Rollee de cette entreprise est désactivé : réactivez-le "
                "dans Intégrations."
            )
        return lie
    branchement = pour_dossier(services.branchements, dossier.tenant_id, dossier.id, TYPE_ROLLEE)
    if branchement is not None:
        return branchement
    actifs = [
        b
        for b in services.branchements.lister(dossier.tenant_id)
        if b.type == TYPE_ROLLEE and b.actif
    ]
    if len(actifs) == 1:
        return actifs[0]
    if not actifs:
        raise RolleeNonBranche(
            "Rollee n'est pas encore branché : votre gestionnaire l'ajoute dans Intégrations."
        )
    raise RolleeNonBranche(
        "Plusieurs comptes Rollee : votre gestionnaire choisit lequel sert votre entreprise."
    )


def client_du_branchement(services: ServicesRollee, branchement: Branchement) -> RolleeHttpClient:
    garder = garder_parametre(services.branchements, branchement, "jeton", "rollee")
    return services.fabrique(branchement, garder)


async def ouvrir_session(services: ServicesRollee, dossier: Dossier) -> Session:
    branchement = branchement_du_dossier(services, dossier)
    client = client_du_branchement(services, branchement)
    try:
        utilisateur = services.comptes.utilisateur(dossier.id)
        if utilisateur is None:
            cree = await client.creer_utilisateur({"dossier_id": str(dossier.id)})
            utilisateur = UtilisateurRollee(dossier.id, str(cree["id"]), branchement.id)
            services.comptes.enregistrer_utilisateur(utilisateur, services.maintenant())
            reponse = cree if cree.get("link") else None
        else:
            reponse = None
        if reponse is None:
            reponse = await client.nouvelle_session(utilisateur.rollee_user_id)
    finally:
        await client.aclose()
    expire = reponse.get("session_expires_at")
    return Session(lien=str(reponse["link"]), expire_le=str(expire) if expire else None)


def _branchement_du_user(
    services: ServicesRollee, dossier: Dossier, utilisateur: UtilisateurRollee
) -> Branchement:
    actifs = services.branchements.lister(dossier.tenant_id)
    lie = next((b for b in actifs if b.id == utilisateur.branchement_id and b.actif), None)
    if lie is None:
        raise RolleeNonBranche(
            "Le branchement Rollee de cette entreprise est désactivé : réactivez-le "
            "dans Intégrations."
        )
    return lie


async def _relire_un(
    services: ServicesRollee, dossier: Dossier, utilisateur: UtilisateurRollee
) -> None:
    """Remplace les plateformes de ce compte Rollee, sans toucher aux autres.
    Avec des noms attendus, seul le compte à ce nom est retenu. Un compte au
    nom d'un autre chauffeur n'est pas relié du tout : il n'est pas enregistré,
    personne ne le voit (AXE-923)."""
    client = client_du_branchement(services, _branchement_du_user(services, dossier, utilisateur))
    try:
        bruts = await client.comptes(utilisateur.rollee_user_id)
        comptes = [
            await _compte_relu(client, dossier, utilisateur, brut, services)
            for brut in bruts
            if brut.get("id")
        ]
    finally:
        await client.aclose()
    siens = [compte for compte in comptes if not compte.titulaire_autre]
    services.comptes.remplacer_comptes(dossier.id, siens, utilisateur.rollee_user_id)


async def _compte_relu(
    client: RolleeHttpClient,
    dossier: Dossier,
    utilisateur: UtilisateurRollee,
    brut: dict[str, Any],
    services: ServicesRollee,
) -> CompteRelie:
    connus = {c.account_id: c for c in services.comptes.comptes(dossier.id)}
    retenu, autre = await titulaire_du_compte(client, str(brut["id"]), utilisateur)
    return depuis_rollee(
        dossier.id,
        brut,
        connus.get(str(brut.get("id"))),
        services.maintenant(),
        utilisateur.rollee_user_id,
        retenu,
        autre,
    )


async def titulaire_du_compte(
    client: RolleeHttpClient, account_id: str, utilisateur: UtilisateurRollee
) -> tuple[bool, bool]:
    attendus = utilisateur.noms_attendus
    if attendus is None:
        return True, False
    try:
        profil = await client.profil(account_id)
    except RolleeIndisponible as exc:
        if exc.statut is not None and exc.statut >= 500:
            return retenir_compte("", frozenset(attendus), True)
        raise
    nom = nom_du_profil(profil if isinstance(profil, dict) else {})
    from axelcompta.rapprochement_rollee_service import cle_empreintes

    return retenir_compte(empreinte(cle_empreintes(), nom), frozenset(attendus), False)


async def relire_comptes(services: ServicesRollee, dossier: Dossier) -> list[CompteRelie]:
    """Chaque compte Rollee du chauffeur est relu. Leurs plateformes
    s'additionnent : en retirer un ne vide pas les autres. Sans user,
    liste vide, sans appel."""
    utilisateurs = services.comptes.utilisateurs(dossier.id)
    if not utilisateurs:
        branchement_du_dossier(services, dossier)  # RolleeNonBranche si rien n'est branché
        return []
    for utilisateur in utilisateurs:
        await _relire_un(services, dossier, utilisateur)
    services.comptes.retirer_comptes_sans_user(dossier.id)
    return services.comptes.comptes(dossier.id)


async def synchroniser_dossier(services: ServicesRollee, dossier: Dossier) -> str:
    """Relit chez Rollee les comptes de plateforme d'une entreprise déjà
    reliée. Sans user Rollee, le bouton lance le rapprochement à la place."""
    if not services.comptes.utilisateurs(dossier.id):
        return "Aucun compte Rollee relié : rien à synchroniser."
    return _phrase_synchro(await relire_comptes(services, dossier))


def _phrase_synchro(comptes: list[CompteRelie]) -> str:
    if not comptes:
        return "Rollee synchronisé : aucun compte de plateforme."
    phrase = f"Rollee synchronisé : {', '.join(c.nom for c in comptes)}."
    perdus = [c.nom for c in comptes if c.etat == "a_reconnecter"]
    if len(perdus) == 1:
        phrase = f"{phrase} {perdus[0]} est à reconnecter."
    elif perdus:
        phrase = f"{phrase} {len(perdus)} à reconnecter."
    return _preciser_titulaires(phrase, comptes)


def _preciser_titulaires(phrase: str, comptes: list[CompteRelie]) -> str:
    """Un compte au nom d'un autre chauffeur n'est jamais dans `comptes`
    (AXE-923) : la phrase n'en parle pas."""
    inconnus = sum(1 for c in comptes if not c.retenu and not c.titulaire_autre)
    if inconnus:
        phrase = f"{phrase} {inconnus} profil(s) illisible(s), compte non retenu."
    return phrase


# --- AXE-820 : webhooks et rattrapage quotidien -----------------------------

Notifier = Callable[[DossierId], None]
ReleverRevenus = Callable[[Dossier], Awaitable[str]]


def secret_webhook(parametres_chiffres: str) -> str:
    """Le secret de signature du branchement (posé par `webhooks_rollee`)."""
    parametres: dict[str, str] = json.loads(dechiffrer(parametres_chiffres))
    return parametres.get("secret_webhook", "")


@dataclass
class Suivi:
    """Ce dont le traitement a besoin, en plus des services Rollee."""

    services: ServicesRollee
    evenements: EvenementsRolleeRepository
    dossiers: DossierRepository
    notifier: Notifier
    relever_revenus: ReleverRevenus | None = None  # AXE-821
    # Rattrapage de 4 h : tout l'historique, pas la fenêtre de deux semaines.
    relever_historique: ReleverRevenus | None = None
    # AXE-911 : un webhook d'un user Rollee inconnu lance son rapprochement.
    # AXE-966 : tous les inconnus d'un lot passent ensemble ; pour chacun,
    # les flottes (branchements) d'où viennent ses webhooks.
    rapprocher_inconnus: (
        Callable[[TenantId, Mapping[str, Collection[str]]], Awaitable[str]] | None
    ) = None


async def _suivre_dossier(
    suivi: Suivi, dossier: Dossier, donnees: bool, complet: bool = False
) -> str:
    """Relit les comptes ; prévient le chauffeur d'une plateforme perdue ;
    relève les revenus si des données sont prêtes."""
    avant = {c.account_id: c.etat for c in suivi.services.comptes.comptes(dossier.id)}
    comptes = await relire_comptes(suivi.services, dossier)
    perdus = [
        c
        for c in comptes
        if c.etat == "a_reconnecter" and avant.get(c.account_id) != "a_reconnecter"
    ]
    if perdus:
        suivi.notifier(dossier.id)
    relever = (
        suivi.relever_historique
        if complet and suivi.relever_historique is not None
        else suivi.relever_revenus
    )
    if donnees and relever is not None:
        return await relever(dossier)
    return f"{dossier.id} : {len(comptes)} compte(s), {len(perdus)} à reconnecter"


@dataclass
class _Lot:
    """Les événements d'un lot, regroupés : un dossier n'est relu qu'une
    fois, et les users inconnus passent ensemble (AXE-966)."""

    dossiers: dict[DossierId, Dossier] = field(default_factory=dict)
    avec_donnees: set[DossierId] = field(default_factory=set)
    inconnus: dict[str, set[str]] = field(default_factory=dict)
    # Pour chaque événement : ce qui le concerne, dans l'ordre de ses users.
    cibles: dict[str, list[str]] = field(default_factory=dict)
    textes: dict[str, str] = field(default_factory=dict)


_INCONNUS = "inconnus"


def _regrouper(suivi: Suivi, evenements: Sequence[EvenementRollee]) -> _Lot:
    lot = _Lot()
    for evenement in evenements:
        if evenement.type not in TYPES_COMPTES | TYPES_DONNEES:
            lot.cibles[evenement.id] = []
            continue
        cibles: list[str] = []
        for user in evenement.users:
            dossier_id = suivi.services.comptes.dossier_du_user(user)
            dossier = suivi.dossiers.obtenir(dossier_id) if dossier_id else None
            if dossier is None or dossier.tenant_id != evenement.tenant_id:
                if suivi.rapprocher_inconnus is None:
                    cle = f"user:{user}"
                    lot.textes[cle] = f"user {user} inconnu"
                else:
                    cle = _INCONNUS
                    lot.inconnus.setdefault(user, set()).add(evenement.branchement_id)
            else:
                cle = f"dossier:{dossier.id}"
                lot.dossiers.setdefault(dossier.id, dossier)
                if evenement.type in TYPES_DONNEES:
                    lot.avec_donnees.add(dossier.id)
            if cle not in cibles:
                cibles.append(cle)
        lot.cibles[evenement.id] = cibles
    return lot


async def _traiter_lot(suivi: Suivi, tenant_id: TenantId, lot: _Lot) -> None:
    """Chaque dossier une fois, revenus compris si un de ses événements
    porte des données ; puis les inconnus en un seul rapprochement. Une
    erreur reste à ce qu'elle touche."""
    for dossier_id, dossier in lot.dossiers.items():
        try:
            texte = await _suivre_dossier(suivi, dossier, dossier_id in lot.avec_donnees)
        except Exception as exc:  # noqa: BLE001 — un dossier en échec ne bloque pas les autres
            texte = f"erreur : {type(exc).__name__} : {exc}"
        lot.textes[f"dossier:{dossier_id}"] = texte
    if lot.inconnus and suivi.rapprocher_inconnus is not None:
        try:
            texte = await suivi.rapprocher_inconnus(tenant_id, lot.inconnus)
        except Exception as exc:  # noqa: BLE001
            texte = f"erreur : {type(exc).__name__} : {exc}"
        lot.textes[_INCONNUS] = texte


def _resultat(evenement: EvenementRollee, lot: _Lot) -> str:
    if evenement.type not in TYPES_COMPTES | TYPES_DONNEES:
        METRIQUES.incrementer("rollee_evenement_inconnu", type=evenement.type)
        return f"ignoré ({evenement.type})"
    morceaux = [lot.textes.get(cle, "non traité") for cle in lot.cibles[evenement.id]]
    resultat = " ; ".join(morceaux) or "aucun user"
    if resultat.startswith("erreur :"):
        METRIQUES.incrementer("rollee_evenement_echec", type=evenement.type)
    return resultat


def traiter_evenements(suivi: Suivi, tenant_id: TenantId, limite: int = 200) -> str:
    """Job `rollee` de la file : chaque webhook gardé est traité une fois.
    Les événements du lot sont regroupés (AXE-966) : Rollee envoie souvent
    des dizaines de webhooks pour le même user, et chacun relisait tout.
    Une erreur est notée sur les événements qu'elle touche ; le rattrapage
    repasse."""
    evenements = suivi.evenements.a_traiter(tenant_id, limite)
    if not evenements:
        return resume([])
    lot = _regrouper(suivi, evenements)
    asyncio.run(_traiter_lot(suivi, tenant_id, lot))
    traites = []
    for evenement in evenements:
        resultat = _resultat(evenement, lot)
        suivi.evenements.marquer_traite(evenement.id, resultat, suivi.services.maintenant())
        traites.append(resultat)
    return resume(traites)


def rattraper(suivi: Suivi) -> list[str]:
    """Tâche quotidienne : chaque dossier relié est relu, webhook ou pas
    (Rollee abandonne un webhook après 3 essais)."""
    lignes = []
    for dossier_id in suivi.services.comptes.dossiers_relies():
        dossier = suivi.dossiers.obtenir(dossier_id)
        if dossier is None:
            continue
        try:
            lignes.append(asyncio.run(_suivre_dossier(suivi, dossier, donnees=True, complet=True)))
        except Exception as exc:  # noqa: BLE001 — un dossier en échec ne bloque pas les autres
            lignes.append(f"{dossier_id} : ECHEC {type(exc).__name__} : {exc}")
    return lignes


def suivi_postgres(engine: Engine) -> Suivi:
    """Câblage réel, rôle propriétaire (worker, tâches planifiées)."""
    notifications = PostgresNotificationRepository(engine)

    def notifier(dossier_id: DossierId) -> None:
        notifications.enregistrer(
            NotificationEnvoyee(
                id=str(uuid.uuid4()),
                dossier_id=dossier_id,
                type=TYPE_PLATEFORME_A_RECONNECTER,
                envoye_le=datetime.now(UTC),
                ecriture_ids=(),
            )
        )

    # Import différé : `revenus_rollee` s'appuie sur ce module (AXE-821).
    from axelcompta.rapprochement_rollee_service import rapprocher_inconnus
    from axelcompta.revenus_rollee import depots_postgres, relever_revenus

    services = ServicesRollee(PostgresBranchements(engine), PostgresComptesRollee(engine))
    depots = depots_postgres(engine)
    return Suivi(
        services=services,
        evenements=PostgresEvenementsRollee(engine),
        dossiers=PostgresDossierRepository(engine),
        notifier=notifier,
        relever_revenus=lambda d: relever_revenus(services, depots, d, date.today()),
        relever_historique=lambda d: relever_revenus(
            services, depots, d, date.today(), complet=True
        ),
        rapprocher_inconnus=lambda tenant_id, users: rapprocher_inconnus(engine, tenant_id, users),
    )


# --- AXE-820 : réception d'un webhook (route publique, sans identité) ----------

Reception = Literal["inconnu", "refuse", "illisible", "garde", "deja_recu"]


class DepotReception(Protocol):
    def branchement(self, branchement_id: str) -> tuple[TenantId, str] | None:
        """Portefeuille et paramètres chiffrés d'un branchement Rollee actif."""
        ...

    def garder(self, evenement: EvenementRollee) -> bool: ...

    def demander_traitement(self, tenant_id: TenantId) -> None: ...


class ReceptionPostgres:
    """Rôle web : la fonction `axelcompta_webhook_rollee` pour trouver le
    branchement, puis le contexte RLS de son portefeuille pour écrire."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def branchement(self, branchement_id: str) -> tuple[TenantId, str] | None:
        return branchement_pour_webhook(self._engine, branchement_id)

    def garder(self, evenement: EvenementRollee) -> bool:
        with contexte_identite(dossier_id=None, tenant_id=evenement.tenant_id):
            return PostgresEvenementsRollee(self._engine).garder(evenement)

    def demander_traitement(self, tenant_id: TenantId) -> None:
        with contexte_identite(dossier_id=None, tenant_id=tenant_id):
            FilePostgres(self._engine).demander(tenant_id, JOB_ROLLEE)


def recevoir(
    depot: DepotReception,
    branchement_id: str,
    corps: bytes,
    signature: str | None,
    maintenant: datetime,
) -> Reception:
    """Vérifie, garde, dépose un job. Rien de long : Rollee abandonne au-delà
    de 10 secondes. Un webhook rejoué n'est gardé ni traité deux fois."""
    trouve = depot.branchement(branchement_id)
    if trouve is None:
        return "inconnu"
    tenant_id, parametres_chiffres = trouve
    if not signature_valide(secret_webhook(parametres_chiffres), corps, signature):
        METRIQUES.incrementer("rollee_webhook_refuse")
        return "refuse"
    try:
        evenement = lire(corps, tenant_id, branchement_id, maintenant)
    except EvenementIllisible:
        return "illisible"
    METRIQUES.incrementer("rollee_webhook_recu", type=evenement.type)
    if not depot.garder(evenement):
        return "deja_recu"
    depot.demander_traitement(tenant_id)
    return "garde"
