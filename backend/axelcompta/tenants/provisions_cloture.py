"""Saisies de clôture du chauffeur : estimations de CCA et de FNP pour
l'exercice ouvert, et registre des immobilisations (AXE-802).

Les estimations sont remplaçables tant que l'exercice n'est pas clos : ce
n'est pas une écriture validée, seulement le montant qu'il demande de
provisionner (doc 06 §5 point 5). Le registre, lui, est en ajout seul : une
fiche ne se modifie pas, une cession s'y ajoute. La clôture transforme les
deux en écritures d'inventaire.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod

from axelcompta.closing.immobilisations import Cession, Immobilisation
from axelcompta.closing.models import ProvisionCloture
from axelcompta.core.errors import Conflit
from axelcompta.core.ids import DossierId, TenantId


class ImmobilisationConnue(Conflit):
    """Fiche déjà enregistrée, ou bien déjà cédé : le registre ne se réécrit pas."""


class ProvisionsClotureRepository(ABC):
    @abstractmethod
    def lister(
        self, tenant_id: TenantId, dossier_id: DossierId, annee: int
    ) -> tuple[ProvisionCloture, ...]:
        """Dans l'ordre de saisie. Vide si rien n'a été enregistré."""

    @abstractmethod
    def remplacer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        annee: int,
        provisions: tuple[ProvisionCloture, ...],
    ) -> None:
        """Remplace toute la liste de l'exercice. Une liste vide l'efface."""

    @abstractmethod
    def lister_immobilisations(
        self, tenant_id: TenantId, dossier_id: DossierId
    ) -> tuple[Immobilisation, ...]:
        """Tout le registre du dossier, cessions comprises, par mise en service."""

    @abstractmethod
    def ajouter_immobilisation(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation: Immobilisation
    ) -> None:
        """Lève `ImmobilisationConnue` si l'identifiant existe déjà."""

    @abstractmethod
    def enregistrer_cession(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation_id: str, cession: Cession
    ) -> None:
        """Lève `ImmobilisationConnue` si le bien est déjà cédé ou inconnu."""


class InMemoryProvisionsClotureRepository(ProvisionsClotureRepository):
    def __init__(self) -> None:
        self._par_exercice: dict[tuple[str, str, int], tuple[ProvisionCloture, ...]] = {}
        self._immobilisations: dict[tuple[str, str], dict[str, Immobilisation]] = {}

    def lister(
        self, tenant_id: TenantId, dossier_id: DossierId, annee: int
    ) -> tuple[ProvisionCloture, ...]:
        return self._par_exercice.get((tenant_id, dossier_id, annee), ())

    def remplacer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        annee: int,
        provisions: tuple[ProvisionCloture, ...],
    ) -> None:
        cle = (tenant_id, dossier_id, annee)
        if provisions:
            self._par_exercice[cle] = provisions
        else:
            self._par_exercice.pop(cle, None)

    def lister_immobilisations(
        self, tenant_id: TenantId, dossier_id: DossierId
    ) -> tuple[Immobilisation, ...]:
        fiches = self._immobilisations.get((tenant_id, dossier_id), {}).values()
        return tuple(sorted(fiches, key=lambda i: (i.mise_en_service, i.id)))

    def ajouter_immobilisation(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation: Immobilisation
    ) -> None:
        registre = self._immobilisations.setdefault((tenant_id, dossier_id), {})
        if immobilisation.id in registre:
            raise ImmobilisationConnue("Ce bien est déjà au registre.")
        registre[immobilisation.id] = immobilisation

    def enregistrer_cession(
        self, tenant_id: TenantId, dossier_id: DossierId, immobilisation_id: str, cession: Cession
    ) -> None:
        registre = self._immobilisations.get((tenant_id, dossier_id), {})
        fiche = registre.get(immobilisation_id)
        if fiche is None or fiche.cession is not None:
            raise ImmobilisationConnue("Ce bien est inconnu ou déjà cédé.")
        registre[immobilisation_id] = dataclasses.replace(fiche, cession=cession)
