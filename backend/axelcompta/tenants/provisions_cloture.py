"""Estimations de CCA et de FNP saisies par le chauffeur, pour l'exercice ouvert.

Remplaçables tant que l'exercice n'est pas clos : ce n'est pas une écriture
validée, seulement le montant qu'il demande de provisionner (doc 06 §5
point 5). La clôture les transforme en écritures d'inventaire.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from axelcompta.closing.models import ProvisionCloture
from axelcompta.core.ids import DossierId, TenantId


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


class InMemoryProvisionsClotureRepository(ProvisionsClotureRepository):
    def __init__(self) -> None:
        self._par_exercice: dict[tuple[str, str, int], tuple[ProvisionCloture, ...]] = {}

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
