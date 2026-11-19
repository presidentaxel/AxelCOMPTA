"""Le passage OCR d'un portefeuille (AXE-943).

Composition root : lancé par le worker (job `ocr_documents` après un dépôt,
et chaque heure en rattrapage), avec le rôle propriétaire. Pour chaque
fiche active :

* un document « à lire » d'une catégorie connue est lu (Haiku, puis Sonnet
  si un contrôle échoue, puis un humain) ;
* un document rangé en « Autre » est d'abord classé : sa nature et son
  exercice le rangent dans sa carte, puis il est lu comme tel.

Un document n'est lu qu'une fois par version des consignes : un document
« à vérifier » attend un humain, il ne repart pas chaque heure. Au-delà du
plafond du mois (`AXELCOMPTA_OCR_PLAFOND_MOIS_USD`), plus rien ne part.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from axelcompta.core.ids import TenantId
from axelcompta.depot_documents_import import emplacement_classe
from axelcompta.tenants.fiches_import import (
    DocumentImport,
    FicheImport,
    lire_emplacement,
    reclasser,
)
from axelcompta.tenants.fiches_import_depot import FichesImportRepository
from axelcompta.tenants.fiches_import_etat import exercices

from .categories import Contexte
from .client import MEDIA_LISIBLES
from .lecture import VERSION, Appeler, lire, meta, traitement
from .pages import dernieres_pages
from .registre import REGISTRE, categorie_ocr

VARIABLE_ACTIF = "AXELCOMPTA_OCR_ACTIF"
VARIABLE_PLAFOND = "AXELCOMPTA_OCR_PLAFOND_MOIS_USD"
PLAFOND_MOIS_USD = 20.0
TAILLE_MAX = 20 * 1024 * 1024  # un PDF plus gros dépasse la requête une fois encodé
DOCUMENTS_PAR_PASSAGE = 60


def ocr_actif() -> bool:
    return os.environ.get(VARIABLE_ACTIF) == "1"


def plafond_mois() -> float:
    return float(os.environ.get(VARIABLE_PLAFOND, PLAFOND_MOIS_USD))


def media_type(contenu: bytes) -> str:
    """Le type lu dans les premiers octets, pas dans le nom."""
    if contenu.startswith(b"%PDF"):
        return "application/pdf"
    if contenu.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenu.startswith(b"\x89PNG"):
        return "image/png"
    if contenu.startswith(b"GIF8"):
        return "image/gif"
    if contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _deja_lu(donnees: Mapping[str, object] | None, cle: str) -> bool:
    lecture = (donnees or {}).get(cle)
    return isinstance(lecture, dict) and lecture.get("version") == VERSION


def a_lire(document: DocumentImport) -> bool:
    """Un document que l'OCR doit lire maintenant."""
    if document.statut_traitement != "a_traiter" or document.taille > TAILLE_MAX:
        return False
    if document.categorie == "autre":
        return not _deja_lu(document.donnees, "ocr_classement")
    return document.categorie in REGISTRE and not _deja_lu(document.donnees, "ocr")


def depense_du_mois(documents: Iterable[DocumentImport], maintenant: datetime) -> float:
    """Ce que l'OCR a coûté ce mois-ci, lu sur les documents."""
    mois = maintenant.strftime("%Y-%m")
    total = 0.0
    for document in documents:
        for cle in ("ocr", "ocr_classement"):
            lecture = (document.donnees or {}).get(cle)
            if isinstance(lecture, dict) and str(lecture.get("le", "")).startswith(mois):
                total += float(lecture.get("cout_usd") or 0)
    return total


def contexte(
    fiche: FicheImport, documents: Sequence[DocumentImport], exercice: int | None
) -> Contexte:
    fec = next(
        (
            d.donnees
            for d in documents
            if d.categorie == "fec"
            and d.exercice == exercice
            and (d.donnees or {}).get("type") == "fec"
        ),
        None,
    )
    return Contexte(fiche.champs.get("siren") or None, exercice, fec, fiche.champs)


@dataclass
class Bilan:
    lus: int = 0
    a_verifier: int = 0
    ranges: int = 0
    cout_usd: float = 0.0
    plafond_atteint: bool = False

    def phrase(self) -> str:
        if not (self.lus or self.ranges or self.plafond_atteint):
            return ""
        texte = (
            f"OCR : {self.lus} document(s) lu(s), {self.a_verifier} à vérifier, "
            f"{self.ranges} rangé(s), {self.cout_usd:.2f} $"
        )
        return texte + (" ; plafond du mois atteint" if self.plafond_atteint else "")


def lire_document(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    document: DocumentImport,
    contenu: bytes,
    appeler: Appeler,
    maintenant: datetime,
    bilan: Bilan,
) -> DocumentImport:
    """Le document après sa lecture (et son classement s'il était en « Autre »)."""
    media = media_type(contenu)
    if media not in MEDIA_LISIBLES:
        return _illisible(document, maintenant)
    if document.categorie == "autre":
        document = _classer(fiche, documents, document, contenu, media, appeler, maintenant, bilan)
    categorie = REGISTRE.get(document.categorie)
    if categorie is None or document.statut_traitement != "a_traiter":
        return document
    ctx = contexte(fiche, documents, document.exercice)
    if categorie.inutile_avec_fec and ctx.fec is not None:
        return _garde_sans_lecture(document, maintenant)
    if categorie.dernieres_pages and media == "application/pdf":
        contenu = dernieres_pages(contenu, categorie.dernieres_pages)
    lecture = lire(categorie, contenu, media, ctx, appeler)
    bilan.cout_usd += lecture.cout_usd
    bilan.lus += 1
    bilan.a_verifier += not lecture.acceptee
    statut, resume, donnees = traitement(categorie, lecture, document.donnees, maintenant)
    return replace(document, statut_traitement=statut, resume=resume, donnees=donnees)  # type: ignore[arg-type]


SANS_LECTURE = "Gardé sans lecture : le FEC du même exercice est lu, il dit déjà tout."


def _garde_sans_lecture(document: DocumentImport, maintenant: datetime) -> DocumentImport:
    """AXE-999 : un grand livre dont le FEC est lu n'apprend rien de plus ;
    il est gardé, traité, sans appel ni coût."""
    marque = {
        "version": VERSION,
        "le": maintenant.isoformat(timespec="seconds"),
        "cout_usd": 0.0,
        "a_verifier": False,
        "controles": [],
        "essais": [],
    }
    donnees = {**(document.donnees or {}), "ocr": marque}
    return replace(document, statut_traitement="traite", resume=SANS_LECTURE, donnees=donnees)


ILLISIBLE = "Format que l'OCR ne lit pas (seuls les PDF et les images le sont) : à lire à la main."


def _illisible(document: DocumentImport, maintenant: datetime) -> DocumentImport:
    """Un tableur, un fichier tronqué… : marqué une fois, sans appel ni
    coût, pour qu'il ne reste pas « sera lu par l'OCR » indéfiniment."""
    cle = "ocr_classement" if document.categorie == "autre" else "ocr"
    marque = {
        "version": VERSION,
        "le": maintenant.isoformat(timespec="seconds"),
        "cout_usd": 0.0,
        "a_verifier": True,
        "controles": [ILLISIBLE],
        "essais": [],
    }
    donnees = {**(document.donnees or {}), cle: marque}
    return replace(document, resume=f"À vérifier par un humain : {ILLISIBLE}", donnees=donnees)


def _classer(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    document: DocumentImport,
    contenu: bytes,
    media: str,
    appeler: Appeler,
    maintenant: datetime,
    bilan: Bilan,
) -> DocumentImport:
    classement = categorie_ocr("autre")
    assert classement is not None
    lecture = lire(classement, contenu, media, contexte(fiche, documents, None), appeler)
    bilan.cout_usd += lecture.cout_usd
    donnees = {**(document.donnees or {}), "ocr_classement": meta(lecture, maintenant)}
    if not lecture.acceptee or lecture.lu is None:
        bilan.a_verifier += 1
        raisons = " ; ".join(lecture.echecs)
        return replace(document, resume=f"À vérifier par un humain : {raisons}", donnees=donnees)
    nature = str(lecture.lu.get("type_document"))
    annee = str(lecture.lu.get("annee_exercice") or "")
    exercice = int(annee) if annee.isdigit() else document.exercice
    section = lire_emplacement(document.emplacement)[0] if document.emplacement else "documents"
    range_ = reclasser(document, emplacement_classe(nature, exercice, section))
    bilan.ranges += 1
    return replace(range_, donnees=donnees, resume=f"Rangé par l'OCR : {nature}.")


def passer(
    fiches: FichesImportRepository,
    tenant_id: TenantId,
    appeler: Appeler,
    maintenant: datetime,
    plafond_usd: float,
    documents_max: int = DOCUMENTS_PAR_PASSAGE,
) -> Bilan:
    """Un passage sur le portefeuille : chaque document à lire, jusqu'au
    plafond du mois ou au nombre maximal par passage."""
    lignes = fiches.lister(tenant_id)
    depense = depense_du_mois((d for _f, docs in lignes for d in docs), maintenant)
    bilan = Bilan()
    for fiche, documents in lignes:
        if fiche.statut == "ignore" or fiche.annulee_le:
            continue
        for document in [d for d in documents if a_lire(d)]:
            if depense + bilan.cout_usd >= plafond_usd:
                bilan.plafond_atteint = True
                return bilan
            if bilan.lus + bilan.ranges >= documents_max:
                return bilan
            _d, contenu = fiches.contenu(tenant_id, document.id)
            lu = lire_document(fiche, documents, document, contenu, appeler, maintenant, bilan)
            if lu is not document:
                fiches.ranger(lu)
                complete = completer_fiche(fiche, documents, lu, maintenant)
                if complete is not None:
                    fiche = fiches.enregistrer(complete).fiche
    return bilan


def completer_fiche(
    fiche: FicheImport,
    documents: Sequence[DocumentImport],
    lu: DocumentImport,
    maintenant: datetime,
) -> FicheImport | None:
    """La fiche avec les champs vides que la lecture remplit ; `None` si
    rien ne change. Une saisie n'est jamais écrasée."""
    categorie = REGISTRE.get(lu.categorie)
    lecture = (lu.donnees or {}).get("lu")
    if categorie is None or lu.statut_traitement != "traite" or not isinstance(lecture, dict):
        return None
    if categorie.exercice_source_seul:
        sources = [
            e.annee
            for e in exercices(fiche.champs, maintenant.date(), documents)
            if e.role == "source"
        ]
        if lu.exercice not in sources:
            return None
    nouveaux = {
        champ: valeur
        for champ, valeur in categorie.champs_fiche(lecture).items()
        if valeur and not (fiche.champs.get(champ) or "").strip()
    }
    if not nouveaux:
        return None
    return replace(fiche, champs={**fiche.champs, **nouveaux}, maj_le=maintenant)
