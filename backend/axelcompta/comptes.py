"""Comptes gestionnaire et chauffeur, via Supabase Auth (doc 17 §9 bloc B,
doc 19 §3). **Exception assumée à ADR-003** (« jamais Supabase Auth ») —
implémentation maison prévue en V1.

À la racine du paquet (doc 18), intentionnellement **hors** du découpage
`axelcompta/*/` défini en doc 03 §3 : pas une nouvelle brique
d'architecture. Étendre l'arbre `tenants`/`api` pour un vrai module de
comptes est une décision de structure (graphe de dépendances, contrat
import-linter) qui n'a pas été prise ici — à faire en remplaçant
Supabase Auth, pas avant.

Supabase est la **seule source de vérité** pour qui a été invité :
chaque utilisateur créé porte `app_metadata.dossier_id`, pas de table
séparée à synchroniser. Simplification assumée par rapport à doc 19 §3.2 :
seuls `non_invité` (absence d'utilisateur), `invité` (créé, e-mail non
confirmé) et `actif` (e-mail confirmé) sont modélisés. `compte_créé`
(onboarding partiel) et `inactif` (seuil d'usage, doc 19 §3.2 : « pas
bloquant pour la démo ») demanderaient un suivi applicatif que Supabase
Auth seul ne fournit pas — hors scope de ce premier découpage.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

import httpx

from axelcompta.core.errors import Conflit, Introuvable
from axelcompta.core.ids import DossierId


class StatutInvitation(Enum):
    INVITE = auto()
    ACTIF = auto()


@dataclass(frozen=True, slots=True)
class Invitation:
    dossier_id: DossierId
    email: str
    statut: StatutInvitation


@dataclass(frozen=True, slots=True)
class MembreCompte:
    """Un gestionnaire du portefeuille. `accepte` est faux tant que le lien
    d'invitation n'a pas été ouvert."""

    email: str
    accepte: bool


class CompteDejaInviteError(Conflit, ValueError):
    """Un compte existe déjà pour ce dossier — pas de double invitation
    silencieuse (doc 08 §2.7)."""


class InvitationAbsente(Introuvable, LookupError):
    """Aucune invitation à renvoyer ou à annuler pour ce dossier."""


class InvitationFermee(Conflit, ValueError):
    """Le compte est déjà ouvert : on ne renvoie ni n'annule l'invitation."""


class MembreInconnu(Introuvable, LookupError):
    """Aucun compte de ce portefeuille ne porte cet e-mail."""


class CompteRepository(ABC):
    """Frontière vers le fournisseur de comptes — Supabase Auth pour la
    démo, implémentation maison prévue en V1 (doc 17 §9 bloc B)."""

    @abstractmethod
    def inviter(
        self, dossier_id: DossierId, email: str, *, verifier_existant: bool = True
    ) -> Invitation:
        """Envoie une invitation réelle (e-mail). Lève `CompteDejaInviteError`
        si ce dossier a déjà un compte. `verifier_existant=False` quand
        l'appelant vient déjà de le vérifier pour tout un lot (`statuts`) :
        évite de relister tous les comptes à chaque invitation."""

    def membres(self, tenant_id: str) -> list[MembreCompte]:
        """Comptes rattachés au portefeuille, avec l'état de l'invitation.
        Vide si le fournisseur ne sait pas les lister."""
        return []

    def inviter_membre(self, tenant_id: str, email: str, role: str = "membre") -> None:
        """Ouvre un compte gestionnaire sur la même organisation."""
        raise NotImplementedError

    def renvoyer(self, dossier_id: DossierId) -> Invitation:
        """Renvoie l'invitation tant que le compte n'est pas ouvert."""
        raise NotImplementedError

    def annuler(self, dossier_id: DossierId) -> None:
        """Retire une invitation encore en attente. Un compte ouvert reste."""
        raise NotImplementedError

    def reinitialiser_mfa(self, tenant_id: str, email: str) -> int:
        """AXE-812 : retire les facteurs de double authentification d'un
        membre du portefeuille ; il en enrôlera un nouveau à sa prochaine
        connexion. Renvoie le nombre de facteurs retirés. Lève
        `MembreInconnu` si l'e-mail n'est pas un membre de ce portefeuille."""
        raise NotImplementedError

    def statuts(self, dossier_ids: Iterable[DossierId]) -> dict[DossierId, Invitation]:
        """Statut de plusieurs dossiers (seuls ceux qui ont été invités
        figurent dans le résultat). Par défaut un appel par dossier ;
        l'implémentation Supabase le fait en une seule lecture des comptes."""
        trouves = {d: self.statut(d) for d in dossier_ids}
        return {d: inv for d, inv in trouves.items() if inv is not None}

    @abstractmethod
    def statut(self, dossier_id: DossierId) -> Invitation | None:
        """`None` si jamais invité pour ce dossier — c'est `non_invité`
        (doc 19 §3.2), représenté par l'absence plutôt qu'un état explicite."""


@dataclass(frozen=True, slots=True)
class SupabaseConfig:
    url: str
    service_role_key: str

    @staticmethod
    def depuis_env() -> SupabaseConfig:
        """Pas de valeur par défaut silencieuse (doc 08 §2.7) : les deux
        variables sont obligatoires ou on échoue tout de suite."""
        url = os.environ.get("SUPABASE_URL")
        cle = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not cle:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquantes (voir .env.example)"
            )
        return SupabaseConfig(url=url, service_role_key=cle)


_PAR_PAGE = 200
_PAGES_MAX = 50


class SupabaseCompteRepository(CompteRepository):
    def __init__(self, config: SupabaseConfig, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=f"{config.url}/auth/v1",
            headers={
                "apikey": config.service_role_key,
                "Authorization": f"Bearer {config.service_role_key}",
            },
            timeout=10.0,
        )

    def inviter(
        self, dossier_id: DossierId, email: str, *, verifier_existant: bool = True
    ) -> Invitation:
        if verifier_existant and self.statut(dossier_id) is not None:
            raise CompteDejaInviteError(f"dossier déjà invité : {dossier_id}")
        reponse = self._client.post("/invite", json={"email": email})
        reponse.raise_for_status()
        # Le lien au dossier va dans `app_metadata`, écrit ici côté serveur
        # (clé service role) : `user_metadata`, que l'invité pourrait
        # modifier lui-même via l'API Auth pour s'attribuer le dossier d'un
        # autre (`/invite` ne permet de poser que `user_metadata`, d'où ce
        # second appel). Le compte n'est utilisable qu'après le clic sur le
        # lien d'invitation, donc après ce PUT.
        utilisateur_id = reponse.json()["id"]
        lien = self._client.put(
            f"/admin/users/{utilisateur_id}", json={"app_metadata": {"dossier_id": dossier_id}}
        )
        lien.raise_for_status()
        return Invitation(dossier_id=dossier_id, email=email, statut=StatutInvitation.INVITE)

    def statut(self, dossier_id: DossierId) -> Invitation | None:
        return self.statuts([dossier_id]).get(dossier_id)

    def statuts(self, dossier_ids: Iterable[DossierId]) -> dict[DossierId, Invitation]:
        voulus = set(dossier_ids)
        resultat: dict[DossierId, Invitation] = {}
        for utilisateur in self._tous_les_utilisateurs():
            dossier_id = utilisateur.get("app_metadata", {}).get("dossier_id")
            if dossier_id in voulus:
                confirme = utilisateur.get("email_confirmed_at") or utilisateur.get("confirmed_at")
                statut = StatutInvitation.ACTIF if confirme else StatutInvitation.INVITE
                resultat[DossierId(dossier_id)] = Invitation(
                    dossier_id=DossierId(dossier_id), email=utilisateur["email"], statut=statut
                )
        return resultat

    def membres(self, tenant_id: str) -> list[MembreCompte]:
        trouves: list[MembreCompte] = []
        for utilisateur in self._tous_les_utilisateurs():
            meta = utilisateur.get("app_metadata") or {}
            if str(meta.get("tenant_id") or "") != tenant_id:
                continue
            email = utilisateur.get("email")
            if not email:
                continue
            confirme = utilisateur.get("email_confirmed_at") or utilisateur.get("confirmed_at")
            trouves.append(MembreCompte(email=email, accepte=bool(confirme)))
        return sorted(trouves, key=lambda membre: membre.email)

    def inviter_membre(self, tenant_id: str, email: str, role: str = "membre") -> None:
        # `/invite` répond 422 sur un e-mail déjà connu : on le dit avant.
        if any(
            (u.get("email") or "").lower() == email.lower() for u in self._tous_les_utilisateurs()
        ):
            raise CompteDejaInviteError(f"un compte existe déjà : {email}")
        reponse = self._client.post("/invite", json={"email": email})
        reponse.raise_for_status()
        utilisateur_id = reponse.json()["id"]
        lien = self._client.put(
            f"/admin/users/{utilisateur_id}",
            json={"app_metadata": {"tenant_id": tenant_id, "role": role}},
        )
        lien.raise_for_status()

    def renvoyer(self, dossier_id: DossierId) -> Invitation:
        utilisateur = self._utilisateur_du_dossier(dossier_id)
        if utilisateur is None:
            raise InvitationAbsente(f"aucune invitation : {dossier_id}")
        if utilisateur.get("email_confirmed_at") or utilisateur.get("confirmed_at"):
            raise InvitationFermee("Le compte est déjà ouvert.")
        email = str(utilisateur["email"])
        reponse = self._client.post("/resend", json={"type": "signup", "email": email})
        reponse.raise_for_status()
        return Invitation(dossier_id=dossier_id, email=email, statut=StatutInvitation.INVITE)

    def annuler(self, dossier_id: DossierId) -> None:
        utilisateur = self._utilisateur_du_dossier(dossier_id)
        if utilisateur is None:
            raise InvitationAbsente(f"aucune invitation : {dossier_id}")
        if utilisateur.get("email_confirmed_at") or utilisateur.get("confirmed_at"):
            raise InvitationFermee("Le compte est déjà ouvert.")
        reponse = self._client.delete(f"/admin/users/{utilisateur['id']}")
        reponse.raise_for_status()

    def reinitialiser_mfa(self, tenant_id: str, email: str) -> int:
        membre = next(
            (
                u
                for u in self._tous_les_utilisateurs()
                if (u.get("email") or "").lower() == email.lower()
                and str((u.get("app_metadata") or {}).get("tenant_id") or "") == tenant_id
            ),
            None,
        )
        if membre is None:
            raise MembreInconnu(f"aucun membre {email} dans ce portefeuille")
        facteurs = membre.get("factors") or []
        for facteur in facteurs:
            reponse = self._client.delete(f"/admin/users/{membre['id']}/factors/{facteur['id']}")
            reponse.raise_for_status()
        return len(facteurs)

    def _utilisateur_du_dossier(self, dossier_id: DossierId) -> dict[str, Any] | None:
        for utilisateur in self._tous_les_utilisateurs():
            meta = utilisateur.get("app_metadata") or {}
            if str(meta.get("dossier_id") or "") == str(dossier_id):
                return utilisateur
        return None

    def _tous_les_utilisateurs(self) -> list[dict[str, Any]]:
        """`GET /admin/users` est **paginé** (50 par page par défaut) et n'a
        pas de filtre par metadata. Avant le 2026-09-22 on ne lisait que la
        première page : au-delà de 50 comptes, un dossier déjà invité passait
        pour non invité et recevait une seconde invitation. Filtrage côté
        client, acceptable pour quelques centaines de comptes."""
        utilisateurs: list[dict[str, Any]] = []
        for page in range(1, _PAGES_MAX + 1):
            reponse = self._client.get("/admin/users", params={"page": page, "per_page": _PAR_PAGE})
            reponse.raise_for_status()
            lot: list[dict[str, Any]] = reponse.json().get("users", [])
            utilisateurs.extend(lot)
            if len(lot) < _PAR_PAGE:
                return utilisateurs
        raise RuntimeError(f"plus de {_PAGES_MAX * _PAR_PAGE} comptes : pagination à revoir")
