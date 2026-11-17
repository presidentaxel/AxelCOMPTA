"""Fiches d'import et documents en Postgres (AXE-941). RLS par portefeuille.

AXE-970 : avec un bucket (`DepotContenus`), le contenu y est écrit avant la
ligne, sous `cle_archive` ; la base ne garde que la clé. Un contenu écrit
dont la ligne échoue reste dans le bucket sans être lu : rien ne se perd.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, Row

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.rls import appliquer_rls

from .fiches_import import DocumentImport, FicheImport, cle_archive
from .fiches_import_depot import DepotContenus, FicheIntrouvable, Instantane, deplacer
from .fiches_import_etat import statut_calcule
from .orm import documents_import, dossiers, fiches_import
from .registres_json import fiche_depuis_json, fiche_vers_json

_COLONNES_DOCUMENT = [c for c in documents_import.c if c.name != "contenu"]


def _fiche(ligne: Row[Any]) -> FicheImport:
    return FicheImport(
        id=ligne.id,
        tenant_id=TenantId(ligne.tenant_id),
        nom=ligne.nom,
        prenom=ligne.prenom,
        cree_par=ligne.cree_par,
        cree_le=ligne.cree_le,
        statut=ligne.statut,
        champs=dict(ligne.champs or {}),
        registre=fiche_depuis_json(ligne.registre) if ligne.registre else None,
        dossier_id=DossierId(ligne.dossier_id) if ligne.dossier_id else None,
        maj_par=ligne.maj_par,
        maj_le=ligne.maj_le,
        annulee_le=ligne.annulee_le,
        annulee_par=ligne.annulee_par or "",
    )


def _document(ligne: Row[Any]) -> DocumentImport:
    return DocumentImport(
        id=ligne.id,
        fiche_id=ligne.fiche_id,
        tenant_id=TenantId(ligne.tenant_id),
        categorie=ligne.categorie,
        exercice=ligne.exercice,
        nom_fichier=ligne.nom_fichier,
        type_mime=ligne.type_mime,
        taille=ligne.taille,
        empreinte=ligne.empreinte,
        depose_par=ligne.depose_par,
        depose_le=ligne.depose_le,
        emplacement=ligne.emplacement,
        statut_traitement=ligne.statut_traitement,
        resume=ligne.resume,
        origine_id=ligne.origine_id,
        cle_stockage=ligne.cle_stockage or "",
        donnees=ligne.donnees,
    )


def _ligne_document(document: DocumentImport, contenu: bytes | None) -> dict[str, Any]:
    return {
        "id": document.id,
        "fiche_id": document.fiche_id,
        "tenant_id": document.tenant_id,
        "categorie": document.categorie,
        "exercice": document.exercice,
        "nom_fichier": document.nom_fichier,
        "type_mime": document.type_mime,
        "taille": document.taille,
        "empreinte": document.empreinte,
        "contenu": contenu,
        "depose_par": document.depose_par,
        "depose_le": document.depose_le,
        "emplacement": document.emplacement,
        "statut_traitement": document.statut_traitement,
        "resume": document.resume,
        "origine_id": document.origine_id,
        "cle_stockage": document.cle_stockage,
        "donnees": document.donnees,
    }


def _valeurs(fiche: FicheImport) -> dict[str, Any]:
    return {
        "tenant_id": fiche.tenant_id,
        "nom": fiche.nom,
        "prenom": fiche.prenom,
        "statut": fiche.statut,
        "champs": dict(fiche.champs),
        "registre": fiche_vers_json(fiche.registre) if fiche.registre else None,
        "dossier_id": fiche.dossier_id,
        "cree_par": fiche.cree_par,
        "cree_le": fiche.cree_le,
        "maj_par": fiche.maj_par or fiche.cree_par,
        "maj_le": fiche.maj_le or fiche.cree_le,
        "annulee_le": fiche.annulee_le,
        "annulee_par": fiche.annulee_par or None,
    }


class PostgresFichesImport:
    """Une connexion par appel : lire une fiche rend aussi ses documents et
    l'état de son dossier (AXE-946)."""

    def __init__(self, engine: Engine, depot: DepotContenus | None = None) -> None:
        self._engine = engine
        self._depot = depot

    def _ranger_contenus(
        self, documents: Sequence[tuple[DocumentImport, bytes]]
    ) -> list[dict[str, Any]]:
        """Les lignes à insérer ; avec un bucket, les contenus y partent
        d'abord, en parallèle (une archive : des centaines de fichiers)."""
        if self._depot is None:
            return [_ligne_document(d, contenu) for d, contenu in documents]
        depot = self._depot
        ranges = [(replace(d, cle_stockage=cle_archive(d)), contenu) for d, contenu in documents]
        with ThreadPoolExecutor(max_workers=8) as envois:
            list(envois.map(lambda dc: depot.ecrire(dc[0].cle_stockage, dc[1]), ranges))
        return [_ligne_document(d, None) for d, _contenu in ranges]

    def lister(self, tenant_id: TenantId) -> list[tuple[FicheImport, list[DocumentImport]]]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            fiches = connexion.execute(
                select(fiches_import)
                .where(fiches_import.c.tenant_id == tenant_id, fiches_import.c.annulee_le.is_(None))
                .order_by(fiches_import.c.maj_le.desc())
            ).all()
            documents = connexion.execute(
                select(*_COLONNES_DOCUMENT)
                .where(documents_import.c.tenant_id == tenant_id)
                .order_by(documents_import.c.depose_le)
            ).all()
        par_fiche: dict[str, list[DocumentImport]] = {}
        for ligne in documents:
            par_fiche.setdefault(ligne.fiche_id, []).append(_document(ligne))
        return [(_fiche(f), par_fiche.get(f.id, [])) for f in fiches]

    def toutes(self, tenant_id: TenantId) -> list[FicheImport]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(fiches_import).where(fiches_import.c.tenant_id == tenant_id)
            ).all()
        return [_fiche(ligne) for ligne in lignes]

    def lire(self, tenant_id: TenantId, fiche_id: str) -> FicheImport:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            return _fiche(_ligne_fiche(connexion, tenant_id, fiche_id))

    def instantane(self, tenant_id: TenantId, fiche_id: str) -> Instantane:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            fiche = _fiche(_ligne_fiche(connexion, tenant_id, fiche_id))
            return _instantane(connexion, fiche, ecrire=False)

    def enregistrer(self, fiche: FicheImport) -> Instantane:
        valeurs = _valeurs(fiche)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(fiches_import)
                .values(id=fiche.id, **valeurs)
                .on_conflict_do_update(
                    index_elements=[fiches_import.c.id],
                    set_={k: v for k, v in valeurs.items() if k not in ("cree_par", "cree_le")},
                )
            )
            return _instantane(connexion, fiche)

    def deposer(self, document: DocumentImport, contenu: bytes) -> Instantane:
        return self.deposer_lot([(document, contenu)])

    def deposer_lot(self, documents: Sequence[tuple[DocumentImport, bytes]]) -> Instantane:
        premier = documents[0][0]
        if any(d.fiche_id != premier.fiche_id for d, _ in documents):
            raise ValueError("Un lot de documents appartient à une seule fiche.")
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            fiche = _fiche(_ligne_fiche(connexion, premier.tenant_id, premier.fiche_id))
            lignes = self._ranger_contenus(documents)
            # L'archive d'abord : ses fichiers la citent (`origine_id`).
            lignes.sort(key=lambda ligne: ligne["origine_id"] is not None)
            connexion.execute(documents_import.insert(), lignes)
            return _instantane(connexion, fiche)

    def contenu(self, tenant_id: TenantId, document_id: str) -> tuple[DocumentImport, bytes]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(documents_import).where(
                    documents_import.c.tenant_id == tenant_id,
                    documents_import.c.id == document_id,
                )
            ).first()
        if ligne is None:
            raise FicheIntrouvable("Document introuvable.")
        if ligne.contenu is not None:
            return _document(ligne), bytes(ligne.contenu)
        contenu = self._depot.lire(ligne.cle_stockage) if self._depot else None
        if contenu is None:
            raise FicheIntrouvable("Contenu du document introuvable dans le stockage.")
        return _document(ligne), contenu

    def ranger(self, document: DocumentImport) -> Instantane:
        if self._depot is not None:
            document = deplacer(self._depot, document)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            fiche = _fiche(_ligne_fiche(connexion, document.tenant_id, document.fiche_id))
            resultat = connexion.execute(
                update(documents_import)
                .where(
                    documents_import.c.tenant_id == document.tenant_id,
                    documents_import.c.id == document.id,
                )
                .values(
                    categorie=document.categorie,
                    exercice=document.exercice,
                    emplacement=document.emplacement,
                    cle_stockage=document.cle_stockage,
                )
            )
            if resultat.rowcount == 0:
                raise FicheIntrouvable("Document introuvable.")
            return _instantane(connexion, fiche)

    def retirer(self, tenant_id: TenantId, fiche_id: str, document_id: str) -> Instantane:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            fiche = _fiche(_ligne_fiche(connexion, tenant_id, fiche_id))
            cles = (
                connexion.execute(
                    select(documents_import.c.cle_stockage).where(
                        documents_import.c.tenant_id == tenant_id,
                        documents_import.c.fiche_id == fiche_id,
                        (documents_import.c.id == document_id)
                        | (documents_import.c.origine_id == document_id),
                    )
                )
                .scalars()
                .all()
            )
            # Les fichiers sortis d'une archive partent avec elle (cascade).
            resultat = connexion.execute(
                delete(documents_import).where(
                    documents_import.c.tenant_id == tenant_id,
                    documents_import.c.fiche_id == fiche_id,
                    documents_import.c.id == document_id,
                )
            )
            if resultat.rowcount == 0:
                raise FicheIntrouvable("Document introuvable.")
            instantane = _instantane(connexion, fiche)
        if self._depot is not None:
            for cle in cles:
                if cle:
                    self._depot.supprimer(cle)
        return instantane


def _ligne_fiche(connexion: Connection, tenant_id: TenantId, fiche_id: str) -> Row[Any]:
    ligne = connexion.execute(
        select(fiches_import).where(
            fiches_import.c.tenant_id == tenant_id, fiches_import.c.id == fiche_id
        )
    ).first()
    if ligne is None or ligne.annulee_le is not None:
        raise FicheIntrouvable("Fiche d'import introuvable.")
    return ligne


def _instantane(connexion: Connection, fiche: FicheImport, ecrire: bool = True) -> Instantane:
    """Les documents de la fiche, si son dossier est créé, et son statut
    calculé (gardé en base à chaque écriture), sur la même connexion."""
    documents = connexion.execute(
        select(*_COLONNES_DOCUMENT)
        .where(
            documents_import.c.tenant_id == fiche.tenant_id,
            documents_import.c.fiche_id == fiche.id,
        )
        .order_by(documents_import.c.depose_le)
    ).all()
    cree = fiche.dossier_id is not None and bool(
        connexion.execute(
            select(select(dossiers.c.id).where(dossiers.c.id == fiche.dossier_id).exists())
        ).scalar()
    )
    lus = [_document(ligne) for ligne in documents]
    statut = statut_calcule(fiche, lus, date.today())
    if ecrire and statut != fiche.statut:
        connexion.execute(
            update(fiches_import).where(fiches_import.c.id == fiche.id).values(statut=statut)
        )
    return Instantane(replace(fiche, statut=statut), lus, cree)
