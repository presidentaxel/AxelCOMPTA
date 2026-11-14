"""Protocole et dépôts mémoire ou fichier des justificatifs (doc 18).

Le stockage Postgres, le cloisonnement par tenant et la RLS vivent dans
`documents/postgres.py`. Ce fichier garde le protocole et les dépôts
utilisés par `api/routes.py` et ses tests.
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

    def lire(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> tuple[bytes, str] | None: ...


class InMemoryJustificatifRepository:
    def __init__(self) -> None:
        self._stockage = StockageMemoire()
        self._extensions: dict[tuple[str, str, str], str] = {}

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
        self._extensions[(tenant_id, dossier_id, ecriture_id)] = extension

    def a_un_justificatif(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> bool:
        return self._stockage.contient(tenant_id, dossier_id, ecriture_id)

    def presents(self, tenant_id: TenantId, dossier_id: DossierId) -> frozenset[EcritureId]:
        return self._stockage.presents(tenant_id, dossier_id)

    def lire(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> tuple[bytes, str] | None:
        contenu = self._stockage.lire(tenant_id, dossier_id, ecriture_id)
        if contenu is None:
            return None
        return contenu, self._extensions.get((tenant_id, dossier_id, ecriture_id), ".jpg")


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

    def lire(
        self, tenant_id: TenantId, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> tuple[bytes, str] | None:
        return self._stockage.lire_piece(tenant_id, dossier_id, ecriture_id)
