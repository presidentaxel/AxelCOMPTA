"""Où vivent les fiches d'import et leurs documents (AXE-941)."""

from __future__ import annotations

from typing import Protocol

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import TenantId

from .fiches_import import DocumentImport, FicheImport


class FicheIntrouvable(Introuvable):
    """Pas de fiche (ou de document) de ce portefeuille sous cet identifiant."""


class FichesImportRepository(Protocol):
    def lister(self, tenant_id: TenantId) -> list[FicheImport]:
        """Les fiches du portefeuille, la plus récemment modifiée d'abord."""
        ...

    def lire(self, tenant_id: TenantId, fiche_id: str) -> FicheImport:
        """`FicheIntrouvable` si elle n'est pas de ce portefeuille."""
        ...

    def enregistrer(self, fiche: FicheImport) -> None:
        """Crée ou remplace la fiche."""
        ...

    def documents(self, tenant_id: TenantId, fiche_id: str) -> list[DocumentImport]: ...

    def deposer(self, document: DocumentImport, contenu: bytes) -> None: ...

    def contenu(self, tenant_id: TenantId, document_id: str) -> tuple[DocumentImport, bytes]:
        """`FicheIntrouvable` si le document n'est pas de ce portefeuille."""
        ...

    def retirer(self, tenant_id: TenantId, document_id: str) -> None: ...


class FichesImportMemoire:
    """Pour les tests."""

    def __init__(self) -> None:
        self.fiches: dict[str, FicheImport] = {}
        self.fichiers: dict[str, tuple[DocumentImport, bytes]] = {}

    def lister(self, tenant_id: TenantId) -> list[FicheImport]:
        siennes = [f for f in self.fiches.values() if f.tenant_id == tenant_id]
        return sorted(siennes, key=lambda f: f.maj_le or f.cree_le, reverse=True)

    def lire(self, tenant_id: TenantId, fiche_id: str) -> FicheImport:
        fiche = self.fiches.get(fiche_id)
        if fiche is None or fiche.tenant_id != tenant_id:
            raise FicheIntrouvable("Fiche d'import introuvable.")
        return fiche

    def enregistrer(self, fiche: FicheImport) -> None:
        self.fiches[fiche.id] = fiche

    def documents(self, tenant_id: TenantId, fiche_id: str) -> list[DocumentImport]:
        return sorted(
            (
                d
                for d, _ in self.fichiers.values()
                if d.tenant_id == tenant_id and d.fiche_id == fiche_id
            ),
            key=lambda d: d.depose_le,
        )

    def deposer(self, document: DocumentImport, contenu: bytes) -> None:
        self.fichiers[document.id] = (document, contenu)

    def contenu(self, tenant_id: TenantId, document_id: str) -> tuple[DocumentImport, bytes]:
        trouve = self.fichiers.get(document_id)
        if trouve is None or trouve[0].tenant_id != tenant_id:
            raise FicheIntrouvable("Document introuvable.")
        return trouve

    def retirer(self, tenant_id: TenantId, document_id: str) -> None:
        self.contenu(tenant_id, document_id)
        del self.fichiers[document_id]
