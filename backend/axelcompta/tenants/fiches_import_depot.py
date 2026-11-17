"""Où vivent les fiches d'import et leurs documents (AXE-941).

AXE-970 : le contenu d'un document vit dans un bucket S3 privé
(`DepotContenus`, clé `cle_archive`), la base n'en garde que la clé. Sans
bucket configuré (poste de développement, tests), il reste en base.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

from axelcompta.core.errors import Introuvable
from axelcompta.core.ids import TenantId

from .fiches_import import DocumentImport, FicheImport, cle_archive
from .fiches_import_etat import statut_calcule


@dataclass(frozen=True, slots=True)
class Instantane:
    """Tout ce que l'écran d'une fiche affiche, lu en une fois (AXE-946)."""

    fiche: FicheImport
    documents: list[DocumentImport]
    dossier_cree: bool


class FicheIntrouvable(Introuvable):
    """Pas de fiche (ou de document) de ce portefeuille sous cet identifiant."""


class DepotContenus(Protocol):
    """Le bucket des documents, réduit à ce qu'il faut."""

    def lire(self, cle: str) -> bytes | None:
        """Le contenu, ou `None` si l'objet n'existe pas."""

    def ecrire(self, cle: str, contenu: bytes) -> None: ...

    def supprimer(self, cle: str) -> None: ...


class ContenusMemoire:
    """Un bucket en mémoire, pour les tests."""

    def __init__(self) -> None:
        self.objets: dict[str, bytes] = {}

    def lire(self, cle: str) -> bytes | None:
        return self.objets.get(cle)

    def ecrire(self, cle: str, contenu: bytes) -> None:
        self.objets[cle] = contenu

    def supprimer(self, cle: str) -> None:
        self.objets.pop(cle, None)


def deplacer(depot: DepotContenus, document: DocumentImport) -> DocumentImport:
    """Un document reclassé change de place dans le bucket, pour que le
    rangement reste lisible (exercice, catégorie)."""
    if not document.cle_stockage:
        return document
    nouvelle = cle_archive(document)
    if nouvelle == document.cle_stockage:
        return document
    contenu = depot.lire(document.cle_stockage)
    if contenu is None:
        raise FicheIntrouvable("Contenu du document introuvable dans le stockage.")
    depot.ecrire(nouvelle, contenu)
    depot.supprimer(document.cle_stockage)
    return replace(document, cle_stockage=nouvelle)


class FichesImportRepository(Protocol):
    """Chaque lecture ou écriture d'une fiche rend son instantané, en une
    seule connexion : la base est loin (~130 ms par aller-retour)."""

    def lister(self, tenant_id: TenantId) -> list[tuple[FicheImport, list[DocumentImport]]]:
        """Les fiches du portefeuille et leurs documents, la plus récemment
        modifiée d'abord."""
        ...

    def lire(self, tenant_id: TenantId, fiche_id: str) -> FicheImport:
        """`FicheIntrouvable` si elle n'est pas de ce portefeuille."""
        ...

    def toutes(self, tenant_id: TenantId) -> list[FicheImport]:
        """Toutes les fiches, annulées comprises (AXE-952 : une fiche annulée
        ne revient pas à la synchro)."""
        ...

    def instantane(self, tenant_id: TenantId, fiche_id: str) -> Instantane: ...

    def enregistrer(self, fiche: FicheImport) -> Instantane:
        """Crée ou remplace la fiche."""
        ...

    def deposer(self, document: DocumentImport, contenu: bytes) -> Instantane: ...

    def deposer_lot(self, documents: Sequence[tuple[DocumentImport, bytes]]) -> Instantane:
        """AXE-970 : plusieurs documents d'une même fiche (une archive et ses
        fichiers, un dépôt en vrac), en une transaction ; tous ou aucun."""
        ...

    def contenu(self, tenant_id: TenantId, document_id: str) -> tuple[DocumentImport, bytes]:
        """`FicheIntrouvable` si le document n'est pas de ce portefeuille."""
        ...

    def ranger(self, document: DocumentImport) -> Instantane:
        """AXE-970 : enregistre la nouvelle catégorie, l'exercice et
        l'emplacement d'un document déjà déposé (son contenu suit)."""
        ...

    def retirer(self, tenant_id: TenantId, fiche_id: str, document_id: str) -> Instantane:
        """Retire le document, et les fichiers sortis de lui si c'est une
        archive."""
        ...


class FichesImportMemoire:
    """Pour les tests. `existe` dit si un dossier est déjà au portefeuille."""

    def __init__(self, existe: Callable[[str], bool] = lambda _id: False) -> None:
        self.fiches: dict[str, FicheImport] = {}
        self.fichiers: dict[str, tuple[DocumentImport, bytes]] = {}
        self._existe = existe

    def _documents(self, tenant_id: TenantId, fiche_id: str) -> list[DocumentImport]:
        return sorted(
            (
                d
                for d, _ in self.fichiers.values()
                if d.tenant_id == tenant_id and d.fiche_id == fiche_id
            ),
            key=lambda d: d.depose_le,
        )

    def lister(self, tenant_id: TenantId) -> list[tuple[FicheImport, list[DocumentImport]]]:
        siennes = [
            f for f in self.fiches.values() if f.tenant_id == tenant_id and f.annulee_le is None
        ]
        siennes.sort(key=lambda f: f.maj_le or f.cree_le, reverse=True)
        return [(f, self._documents(tenant_id, f.id)) for f in siennes]

    def toutes(self, tenant_id: TenantId) -> list[FicheImport]:
        return [f for f in self.fiches.values() if f.tenant_id == tenant_id]

    def lire(self, tenant_id: TenantId, fiche_id: str) -> FicheImport:
        fiche = self.fiches.get(fiche_id)
        if fiche is None or fiche.tenant_id != tenant_id or fiche.annulee_le is not None:
            raise FicheIntrouvable("Fiche d'import introuvable.")
        return fiche

    def _instantane(self, fiche: FicheImport) -> Instantane:
        documents = self._documents(fiche.tenant_id, fiche.id)
        fiche = replace(fiche, statut=statut_calcule(fiche, documents, date.today()))
        self.fiches[fiche.id] = fiche
        cree = fiche.dossier_id is not None and self._existe(fiche.dossier_id)
        return Instantane(fiche, documents, cree)

    def instantane(self, tenant_id: TenantId, fiche_id: str) -> Instantane:
        return self._instantane(self.lire(tenant_id, fiche_id))

    def enregistrer(self, fiche: FicheImport) -> Instantane:
        return self._instantane(fiche)

    def deposer(self, document: DocumentImport, contenu: bytes) -> Instantane:
        self.fichiers[document.id] = (document, contenu)
        return self.instantane(document.tenant_id, document.fiche_id)

    def deposer_lot(self, documents: Sequence[tuple[DocumentImport, bytes]]) -> Instantane:
        premier = documents[0][0]
        self.lire(premier.tenant_id, premier.fiche_id)
        for document, contenu in documents:
            self.fichiers[document.id] = (document, contenu)
        return self.instantane(premier.tenant_id, premier.fiche_id)

    def ranger(self, document: DocumentImport) -> Instantane:
        _avant, contenu = self.contenu(document.tenant_id, document.id)
        self.fichiers[document.id] = (document, contenu)
        return self.instantane(document.tenant_id, document.fiche_id)

    def contenu(self, tenant_id: TenantId, document_id: str) -> tuple[DocumentImport, bytes]:
        trouve = self.fichiers.get(document_id)
        if trouve is None or trouve[0].tenant_id != tenant_id:
            raise FicheIntrouvable("Document introuvable.")
        return trouve

    def retirer(self, tenant_id: TenantId, fiche_id: str, document_id: str) -> Instantane:
        document, _ = self.contenu(tenant_id, document_id)
        if document.fiche_id != fiche_id:
            raise FicheIntrouvable("Document introuvable.")
        del self.fichiers[document_id]
        for autre in [d for d, _ in self.fichiers.values() if d.origine_id == document_id]:
            del self.fichiers[autre.id]
        return self.instantane(tenant_id, fiche_id)
