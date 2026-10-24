"""Adaptateur démo vers `documents/` (doc 18).

Le stockage, le cloisonnement par tenant et la RLS vivent dans le module.
Ce fichier ne fait que garder les deux noms historiques utilisés par
`demo_api` et ses tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.documents.fichier import StockageFichier
from axelcompta.documents.memoire import StockageMemoire
from axelcompta.documents.preparer import preparer


class JustificatifRepository(Protocol):
    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        contenu: bytes,
        extension: str,
    ) -> None: ...

    def a_un_justificatif(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bool: ...

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]: ...


class InMemoryJustificatifRepository:
    def __init__(self) -> None:
        self._stockage = StockageMemoire()

    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        contenu: bytes,
        extension: str,
    ) -> None:
        self._stockage.poser(
            preparer(tenant_id, dossier_id, ecriture_id, contenu, extension), contenu
        )

    def a_un_justificatif(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bool:
        return self._stockage.contient(tenant_id, dossier_id, ecriture_id)

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]:
        return self._stockage.presents(tenant_id, dossier_id)


class FichierJustificatifRepository:
    def __init__(self, racine: Path) -> None:
        self._stockage = StockageFichier(racine)

    def enregistrer(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        ecriture_id: EcritureId,
        contenu: bytes,
        extension: str,
    ) -> None:
        self._stockage.poser(
            preparer(tenant_id, dossier_id, ecriture_id, contenu, extension), contenu
        )

    def a_un_justificatif(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bool:
        return self._stockage.contient(tenant_id, dossier_id, ecriture_id)

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]:
        return self._stockage.presents(tenant_id, dossier_id)
