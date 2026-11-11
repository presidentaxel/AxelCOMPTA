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

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from axelcompta.core.errors import Conflit
from axelcompta.ingestion.comptes_rollee import (
    CompteRelie,
    ComptesRolleeRepository,
    UtilisateurRollee,
    depuis_rollee,
)
from axelcompta.ingestion.providers.rollee import RolleeHttpClient
from axelcompta.tenants.branchements import (
    Branchement,
    BranchementsRepository,
    garder_parametre,
    pour_dossier,
)
from axelcompta.tenants.models import Dossier

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
