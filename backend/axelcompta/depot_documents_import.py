"""Ce qui entre sur une fiche d'import quand on y dépose des fichiers (AXE-947,
AXE-970).

- Un fichier déposé sur un emplacement (« reprise:liasse:2025 ») y est rangé
  tel quel.
- Un dépôt **en vrac sur un exercice** (« Déposer des fichiers de
  l'exercice ») range chaque fichier dans sa catégorie devinée
  (`traitement_documents_import.classer`) ; il se reclasse ensuite.
- Une **archive zip** est gardée intacte (preuve : une archive fiscale est
  signée), et chaque fichier qu'elle contient devient un document de la
  fiche, sorti d'elle (`origine_id`) : l'archive OneUp d'un exercice donne
  son FEC, son grand livre, ses comptes annuels et ses pièces.

- AXE-971 : un fichier dont le contenu est déjà sur la fiche (même
  empreinte) n'est pas ajouté une seconde fois, qu'il vienne seul ou d'une
  archive déposée par-dessus (`sans_doublons`).

Chaque document est lu tout de suite s'il se lit (FEC, QIF). Composition
root (doc 18) : rien n'est écrit ici, la route passe le lot au dépôt.
"""

from __future__ import annotations

import mimetypes
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from axelcompta.tenants.fiches_import import (
    DocumentImport,
    FicheImport,
    document_import,
    emplacement_de,
    lire_emplacement,
)
from axelcompta.tenants.fiches_import_etat import SECTION_PAR_CATEGORIE
from axelcompta.traitement_documents_import import (
    ArchiveIllisible,
    annee_du_nom,
    classer,
    deplier,
    traiter,
)

Lot = list[tuple[DocumentImport, bytes]]


@dataclass(frozen=True, slots=True)
class Fichier:
    nom: str
    type_mime: str
    contenu: bytes


def _lu(document: DocumentImport, contenu: bytes, siren: str | None) -> DocumentImport:
    lu = traiter(document.categorie, document.nom_fichier, contenu, siren)
    return replace(document, statut_traitement=lu.statut, resume=lu.resume, donnees=lu.donnees)


def _emplacement_classe(categorie: str, exercice: int | None, repli: str) -> str:
    """Où ranger un fichier classé : la reprise de son exercice pour une
    pièce comptable, la banque ou les documents administratifs sinon ; un
    fichier que rien ne classe reste dans la section du dépôt (`repli`)."""
    section = repli if categorie == "autre" else SECTION_PAR_CATEGORIE.get(categorie, repli)
    # Un emprunt court sur plusieurs exercices : une seule carte (AXE-989).
    par_exercice = section == "reprise" and categorie != "emprunt"
    return emplacement_de(section, categorie, exercice if par_exercice else None)


def _membres(
    fiche: FicheImport, archive: DocumentImport, contenu: bytes, par: str, le: datetime
) -> tuple[DocumentImport, Lot]:
    """L'archive (lue ou illisible) et les fichiers qui en sortent."""
    siren = fiche.champs.get("siren") or None
    try:
        membres = deplier(contenu)
    except ArchiveIllisible as exc:
        return replace(archive, statut_traitement="illisible", resume=f"Archive : {exc}."), []
    section = lire_emplacement(archive.emplacement)[0]
    lot: Lot = []
    for membre in membres:
        categorie = classer(membre.chemin, membre.contenu)
        exercice = archive.exercice or annee_du_nom(membre.chemin)
        emplacement = _emplacement_classe(categorie, exercice, section)
        nom = f"{Path(archive.nom_fichier).name}/{membre.chemin}"[-200:]
        document = document_import(
            uuid.uuid4().hex,
            fiche,
            emplacement,
            nom,
            mimetypes.guess_type(membre.chemin)[0] or "application/octet-stream",
            membre.contenu,
            par,
            le,
        )
        document = _lu(replace(document, origine_id=archive.id), membre.contenu, siren)
        lot.append((document, membre.contenu))
    resume = f"Archive gardée intacte : {len(lot)} fichier(s) rangé(s) à part."
    return replace(archive, statut_traitement="traite", resume=resume), lot


def _un_fichier(
    fiche: FicheImport, emplacement: str, fichier: Fichier, par: str, le: datetime
) -> Lot:
    document = document_import(
        uuid.uuid4().hex,
        fiche,
        emplacement,
        fichier.nom,
        fichier.type_mime,
        fichier.contenu,
        par,
        le,
    )
    if fichier.contenu[:4] == b"PK\x03\x04" and Path(fichier.nom).suffix.lower() == ".zip":
        archive, membres = _membres(fiche, document, fichier.contenu, par, le)
        return [(archive, fichier.contenu), *membres]
    return [(_lu(document, fichier.contenu, fiche.champs.get("siren") or None), fichier.contenu)]


def depot_sur_emplacement(
    fiche: FicheImport, emplacement: str, fichier: Fichier, par: str, le: datetime
) -> Lot:
    """Un fichier déposé sur une carte ; une archive y est aussi dépliée."""
    return _un_fichier(fiche, emplacement, fichier, par, le)


def depot_sur_exercice(
    fiche: FicheImport, annee: int, fichiers: Sequence[Fichier], par: str, le: datetime
) -> Lot:
    """Des fichiers déposés en vrac sur l'exercice clos en `annee` : chacun
    dans sa catégorie devinée ; un Kbis ou un RIB va dans les documents
    permanents, sans exercice."""
    lot: Lot = []
    for fichier in fichiers:
        categorie = classer(fichier.nom, fichier.contenu)
        emplacement = _emplacement_classe(categorie, annee, "reprise")
        lot += _un_fichier(fiche, emplacement, fichier, par, le)
    return lot


def promus(lot: Lot, existants: Sequence[DocumentImport]) -> list[DocumentImport]:
    """AXE-988 : un fichier déjà sur la fiche en « Autre », redéposé et cette
    fois classé (un récapitulatif Uber déposé avant qu'on sache les lire) :
    la copie déjà là prend le classement et la lecture du nouveau dépôt, au
    lieu que celui-ci soit seulement écarté. Même contenu : même lecture."""
    en_vrac = {d.empreinte: d for d in existants if d.categorie == "autre"}
    sortie = []
    for nouveau, _contenu in lot:
        ancien = en_vrac.get(nouveau.empreinte)
        if ancien is None or nouveau.categorie in ("autre", "archive"):
            continue
        del en_vrac[nouveau.empreinte]
        sortie.append(
            replace(
                ancien,
                categorie=nouveau.categorie,
                emplacement=nouveau.emplacement,
                exercice=nouveau.exercice or ancien.exercice,
                statut_traitement=nouveau.statut_traitement,
                resume=nouveau.resume,
                donnees=nouveau.donnees,
            )
        )
    return sortie


def sans_doublons(lot: Lot, deja: Collection[str]) -> tuple[Lot, list[str]]:
    """AXE-971 : le lot sans ce qui est déjà sur la fiche (`deja` : les
    empreintes de ses documents) ni ce qui revient deux fois dans le dépôt.
    Une archive déjà déposée est écartée avec tout ce qui en sort ; une
    archive nouvelle garde ses fichiers nouveaux, et son résumé compte ce
    qui a été écarté. Rend aussi les noms écartés, pour l'écran."""
    vues = set(deja)
    gardes: Lot = []
    ecartes: list[str] = []
    archives_ecartees: set[str] = set()
    for document, contenu in lot:
        if document.origine_id in archives_ecartees:
            continue
        if document.empreinte in vues:
            ecartes.append(Path(document.nom_fichier).name)
            if document.categorie == "archive" or document.origine_id is None:
                archives_ecartees.add(document.id)
            continue
        vues.add(document.empreinte)
        gardes.append((document, contenu))
    return [_recompter(d, c, gardes, lot) for d, c in gardes], ecartes


def _recompter(
    document: DocumentImport, contenu: bytes, gardes: Lot, lot: Lot
) -> tuple[DocumentImport, bytes]:
    """Le résumé d'une archive dit combien de ses fichiers sont rangés, et
    combien étaient déjà sur la fiche."""
    if document.statut_traitement != "traite" or not any(
        d.origine_id == document.id for d, _ in lot
    ):
        return document, contenu
    ranges = sum(1 for d, _ in gardes if d.origine_id == document.id)
    ecartes = sum(1 for d, _ in lot if d.origine_id == document.id) - ranges
    resume = f"Archive gardée intacte : {ranges} fichier(s) rangé(s) à part"
    resume += f", {ecartes} déjà sur la fiche." if ecartes else "."
    return replace(document, resume=resume), contenu
