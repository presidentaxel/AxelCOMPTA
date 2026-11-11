"""Frontière de persistance des dossiers (doc 03 §3bis). Toute lecture
d'un dossier pour le compte d'un gestionnaire passe par `tenant_id` : c'est
ici, et pas dans chaque route, que l'isolation entre portefeuilles se joue.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime

from axelcompta.core.identite import IdentiteEntreprise
from axelcompta.core.ids import DossierId, TenantId, UserId

from .models import Dossier, Tenant
from .statuts import configuration_de


class DossierRepository(ABC):
    @abstractmethod
    def enregistrer_tenant(self, tenant: Tenant) -> None:
        """Idempotent : un tenant déjà présent est laissé tel quel."""

    @abstractmethod
    def enregistrer(self, dossier: Dossier) -> None:
        """Idempotent sur `dossier.id` : un dossier déjà présent est laissé
        tel quel (pas de mise à jour silencieuse d'une config comptable).
        Lève `ConfigurationInvalide` (statuts.py) avant toute écriture si la
        configuration fiscale n'a pas de sens."""

    def enregistrer_lot(self, lot: Sequence[Dossier]) -> int:
        """Plusieurs dossiers d'un coup (AXE-809) ; renvoie le nombre de créés.
        Tout ou rien là où le stockage le permet (Postgres : une transaction).
        Toutes les configurations sont vérifiées avant la première écriture."""
        for dossier in lot:
            configuration_de(dossier)
        nouveaux = [d for d in lot if self.obtenir(d.id) is None]
        for dossier in lot:
            self.enregistrer(dossier)
        return len(nouveaux)

    @abstractmethod
    def obtenir(self, dossier_id: DossierId) -> Dossier | None:
        """`None` si le dossier n'existe pas."""

    @abstractmethod
    def lister_par_tenant(self, tenant_id: TenantId) -> tuple[Dossier, ...]:
        """Uniquement les dossiers de ce portefeuille, triés par id."""

    @abstractmethod
    def obtenir_tenant(self, tenant_id: TenantId) -> Tenant | None:
        """`None` si le portefeuille n'existe pas."""

    @abstractmethod
    def lister_tenants(self) -> tuple[Tenant, ...]:
        """Tous les portefeuilles, triés par id (tâches planifiées)."""

    @abstractmethod
    def renommer_tenant(self, tenant_id: TenantId, nom: str) -> None:
        """Le nom affiché du portefeuille, choisi par l'organisation."""

    @abstractmethod
    def regler_relance_tenant(self, tenant_id: TenantId, mode: str) -> None:
        """Mode de relance des connexions bancaires du portefeuille."""

    @abstractmethod
    def regler_relance_dossier(self, dossier_id: DossierId, mode: str | None) -> None:
        """Exception pour un dossier ; `None` le remet sur le portefeuille."""

    @abstractmethod
    def poser_forme_juridique(self, dossier_id: DossierId, forme: str) -> None:
        """Remplace la forme juridique après validation par la matrice.
        Sert au rapprochement Sirene : le code INSEE dit SAS ou SARL, pas
        la valeur posée par défaut à la création."""

    @abstractmethod
    def reconfigurer_depuis_sirene(self, dossier: Dossier) -> None:
        """Forme, bornes du premier exercice, activité et éléments à
        confirmer, tirés de Sirene (AXE-834). Lève `ConfigurationInvalide`
        avant d'écrire si la configuration n'a pas de sens."""

    @abstractmethod
    def confirmer_configuration(self, dossier: Dossier, par: UserId, le: datetime) -> None:
        """Le dirigeant a confirmé la configuration (AXE-730) : forme choisie
        et plus rien à confirmer. Tracé au journal d'audit."""

    @abstractmethod
    def enregistrer_identite(
        self, dossier_id: DossierId, identite: IdentiteEntreprise, par: UserId, le: datetime
    ) -> None:
        """Siège, capital et associés saisis par le dirigeant (AXE-846),
        tracés au journal d'audit. Identité déjà vérifiée par l'appelant
        (`identite_saisie.verifier_identite`)."""

    @abstractmethod
    def parametrer_tva(
        self, dossier_id: DossierId, periodicite: str, jour: int, par: UserId, le: datetime
    ) -> None:
        """Périodicité et jour d'échéance de la CA3 (AXE-805), tracés au
        journal d'audit. Valeurs déjà vérifiées par l'appelant."""

    @abstractmethod
    def ouvrir_exercice(self, dossier: Dossier) -> None:
        """Seule mise à jour de configuration admise : à l'ouverture de
        l'exercice suivant (`axelcompta.exercices`), les bornes et les
        régimes du nouvel exercice. Lève `ConfigurationInvalide` avant
        d'écrire si la nouvelle configuration n'a pas de sens."""

    @abstractmethod
    def retirer(self, dossier_id: DossierId) -> None:
        """Sort le dossier de la liste du portefeuille. Les écritures restent."""

    @abstractmethod
    def lister_retires(self, tenant_id: TenantId) -> tuple[Dossier, ...]:
        """Dossiers sortis de la liste, pour les y remettre."""

    @abstractmethod
    def restaurer(self, dossier_id: DossierId) -> None:
        """Remet un dossier retiré dans la liste. Les écritures n'ont pas bougé."""

    @abstractmethod
    def par_contact_nr(self, contact_nr: str) -> Dossier | None:
        """Table de correspondance Digifactory `contact_nr -> dossier`
        (doc 16 §9 point 5)."""
