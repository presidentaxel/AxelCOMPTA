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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

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
)
from axelcompta.ingestion.comptes_rollee_postgres import PostgresComptesRollee
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
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


def _client(services: ServicesRollee, branchement: Branchement) -> RolleeHttpClient:
    garder = garder_parametre(services.branchements, branchement, "jeton", "rollee")
    return services.fabrique(branchement, garder)


async def ouvrir_session(services: ServicesRollee, dossier: Dossier) -> Session:
    branchement = branchement_du_dossier(services, dossier)
    client = _client(services, branchement)
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


async def relire_comptes(services: ServicesRollee, dossier: Dossier) -> list[CompteRelie]:
    """La liste relue chez Rollee remplace celle du dossier. Sans user
    Rollee, rien n'a jamais été relié : liste vide, sans appel (mais
    `RolleeNonBranche` si le chauffeur ne pourrait même pas commencer)."""
    branchement = branchement_du_dossier(services, dossier)
    utilisateur = services.comptes.utilisateur(dossier.id)
    if utilisateur is None:
        return []
    client = _client(services, branchement)
    try:
        bruts = await client.comptes(utilisateur.rollee_user_id)
    finally:
        await client.aclose()
    connus = {c.account_id: c for c in services.comptes.comptes(dossier.id)}
    maintenant = services.maintenant()
    comptes = [
        depuis_rollee(dossier.id, brut, connus.get(str(brut.get("id"))), maintenant)
        for brut in bruts
        if brut.get("id")
    ]
    services.comptes.remplacer_comptes(dossier.id, comptes)
    return comptes


# --- AXE-820 : webhooks et rattrapage quotidien -----------------------------

Notifier = Callable[[DossierId], None]
ReleverRevenus = Callable[[Dossier], str]


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


async def _suivre_dossier(suivi: Suivi, dossier: Dossier, donnees: bool) -> str:
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
    if donnees and suivi.relever_revenus is not None:
        return suivi.relever_revenus(dossier)
    return f"{dossier.id} : {len(comptes)} compte(s), {len(perdus)} à reconnecter"


async def _un_evenement(suivi: Suivi, evenement: EvenementRollee) -> str:
    if evenement.type not in TYPES_COMPTES | TYPES_DONNEES:
        METRIQUES.incrementer("rollee_evenement_inconnu", type=evenement.type)
        return f"ignoré ({evenement.type})"
    morceaux = []
    for user in evenement.users:
        dossier_id = suivi.services.comptes.dossier_du_user(user)
        dossier = suivi.dossiers.obtenir(dossier_id) if dossier_id else None
        if dossier is None or dossier.tenant_id != evenement.tenant_id:
            morceaux.append(f"user {user} inconnu")
            continue
        morceaux.append(await _suivre_dossier(suivi, dossier, evenement.type in TYPES_DONNEES))
    return " ; ".join(morceaux) or "aucun user"


def traiter_evenements(suivi: Suivi, tenant_id: TenantId, limite: int = 200) -> str:
    """Job `rollee` de la file : chaque webhook gardé est traité une fois.
    Une erreur est notée sur l'événement ; le rattrapage du lendemain repasse."""
    traites = []
    for evenement in suivi.evenements.a_traiter(tenant_id, limite):
        try:
            resultat = asyncio.run(_un_evenement(suivi, evenement))
        except Exception as exc:  # noqa: BLE001 — un événement en échec ne bloque pas les autres
            METRIQUES.incrementer("rollee_evenement_echec", type=evenement.type)
            resultat = f"erreur : {type(exc).__name__} : {exc}"
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
            lignes.append(asyncio.run(_suivre_dossier(suivi, dossier, donnees=True)))
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

    return Suivi(
        services=ServicesRollee(PostgresBranchements(engine), PostgresComptesRollee(engine)),
        evenements=PostgresEvenementsRollee(engine),
        dossiers=PostgresDossierRepository(engine),
        notifier=notifier,
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
