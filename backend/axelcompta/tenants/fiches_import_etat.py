"""Ce qui manque à une fiche d'import, ses emplacements de documents et son
statut (AXE-941, AXE-947). Pur.

**Emplacements** : un par document attendu, avec ce que c'est et pourquoi.
Pour un exercice clos depuis 2024 : liasse et FEC (ou balance et grand
livre sans FEC) ; seul le dernier exercice clos est indispensable, il donne
le report à nouveau. En banque : les relevés des mois que Digifactory ne
couvre pas, et le RIB. Documents administratifs : Kbis, statuts, et la
lettre de l'ancien comptable (facultative).

**Statut** : calculé, jamais choisi. « À importer » tant qu'il n'y a que le
nom ; « traitée » quand chaque catégorie est complète et qu'aucun document
n'est illisible ; « en traitement » entre les deux.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Literal

from .fiches_import import (
    CATEGORIES_DOCUMENTS,
    SECTIONS,
    DocumentImport,
    FicheImport,
    Section,
    Statut,
)
from .fiches_import_calculs import bornes
from .fiches_import_listes import lire_associes, total_parts
from .import_dossiers import identifiant

ANNEE_MIN_REPRISE = 2024
SECTION_PAR_CATEGORIE = {
    "liasse": "reprise",
    "fec": "reprise",
    "balance": "reprise",
    "grand_livre": "reprise",
    "releve_bancaire": "banque",
    "rib": "banque",
    "kbis": "documents",
    "statuts": "documents",
    "lettre_comptable": "documents",
    "autre": "documents",
}
CHAMPS_DE_DEPART = frozenset({"nom", "prenom"})


@dataclass(frozen=True, slots=True)
class Emplacement:
    cle: str  # « reprise:liasse:2025 »
    section: str
    categorie: str
    exercice: int | None
    libelle: str
    explication: str
    attendu: bool  # indispensable ; sinon « si vous l'avez »
    documents: tuple[DocumentImport, ...] = ()

    @property
    def rempli(self) -> bool:
        return bool(self.documents)


@dataclass(frozen=True, slots=True)
class Exercice:
    debut: date
    fin: date
    etat: Literal["clos", "en_cours"]

    @property
    def annee(self) -> int:
        return self.fin.year


@dataclass(frozen=True, slots=True)
class EtatSection:
    cle: str
    libelle: str
    complet: bool
    manquants: tuple[str, ...]


def exercices(champs: Mapping[str, str], aujourd_hui: date) -> list[Exercice]:
    """Les exercices clos depuis 2024 et l'exercice en cours."""
    return [
        Exercice(debut, fin, "clos" if fin < aujourd_hui else "en_cours")
        for debut, fin in bornes(champs, aujourd_hui)
        if fin.year >= ANNEE_MIN_REPRISE
    ]


def cle_du_document(document: DocumentImport) -> str:
    """Son emplacement ; pour un document d'avant AXE-947, celui de sa catégorie."""
    if document.emplacement:
        return document.emplacement
    section = SECTION_PAR_CATEGORIE.get(document.categorie, "documents")
    annee = f":{document.exercice}" if section == "reprise" and document.exercice else ""
    return f"{section}:{document.categorie}{annee}"


def _jj(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _reprise(champs: Mapping[str, str], aujourd_hui: date) -> list[Emplacement]:
    clos = [e for e in exercices(champs, aujourd_hui) if e.etat == "clos"]
    dernier = clos[-1].fin if clos else None
    emplacements = []
    for e in clos:
        cle, utile = f"reprise:{{}}:{e.annee}", e.fin == dernier
        quand = f"de l'exercice clos le {_jj(e.fin)}"
        pourquoi = "donne le report à nouveau" if utile else "si vous l'avez"
        emplacements += [
            Emplacement(
                cle.format("liasse"),
                "reprise",
                "liasse",
                e.annee,
                f"Liasse fiscale {e.annee}",
                f"2033 ou 2065 {quand} ; {pourquoi}.",
                utile,
            ),
            Emplacement(
                cle.format("fec"),
                "reprise",
                "fec",
                e.annee,
                f"FEC {e.annee}",
                f"Fichier des écritures {quand}, à demander à l'ancien comptable.",
                utile,
            ),
            Emplacement(
                cle.format("balance"),
                "reprise",
                "balance",
                e.annee,
                f"Balance {e.annee}",
                "Seulement sans FEC.",
                False,
            ),
            Emplacement(
                cle.format("grand_livre"),
                "reprise",
                "grand_livre",
                e.annee,
                f"Grand livre {e.annee}",
                "Seulement sans FEC.",
                False,
            ),
        ]
    emplacements.append(
        Emplacement(
            "reprise:autre",
            "reprise",
            "autre",
            None,
            "Autre document comptable",
            "Bilan, tableau des immobilisations, contrat de LOA, échéancier d'emprunt…",
            False,
        )
    )
    return emplacements


def _releves(champs: Mapping[str, str]) -> Emplacement:
    cle, libelle = "banque:releve_bancaire", "Relevés bancaires"
    debut, historique = champs.get("exercice_debut"), champs.get("debut_historique")
    if not champs.get("contact_digifactory"):
        explication = (
            "La banque n'est pas encore connectée à Digifactory : relevés de "
            "l'exercice en cours, en PDF, QIF ou CSV."
        )
        return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, True)
    if debut and historique and historique > debut:
        veille = date.fromisoformat(historique) - timedelta(days=1)
        explication = (
            f"Du {_jj(date.fromisoformat(debut))} au {_jj(veille)} : avant l'historique "
            "Digifactory. En PDF, QIF ou CSV."
        )
        return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, True)
    explication = "Digifactory couvre l'exercice en cours : seulement si des mois manquent."
    return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, False)


def _vides(champs: Mapping[str, str], aujourd_hui: date) -> list[Emplacement]:
    return [
        *_reprise(champs, aujourd_hui),
        _releves(champs),
        Emplacement("banque:rib", "banque", "rib", None, "RIB", "Du compte professionnel.", True),
        Emplacement(
            "documents:kbis", "documents", "kbis", None, "Kbis", "Extrait de moins de 3 mois.", True
        ),
        Emplacement(
            "documents:statuts",
            "documents",
            "statuts",
            None,
            "Statuts",
            "Dernière version signée.",
            True,
        ),
        Emplacement(
            "documents:lettre_comptable",
            "documents",
            "lettre_comptable",
            None,
            "Lettre de l'ancien expert-comptable",
            "Facultative.",
            False,
        ),
        Emplacement(
            "documents:autre",
            "documents",
            "autre",
            None,
            "Autre document",
            "Tout autre justificatif.",
            False,
        ),
    ]


def emplacements(
    champs: Mapping[str, str], documents: Sequence[DocumentImport], aujourd_hui: date
) -> list[Emplacement]:
    """Chaque emplacement et ses documents ; un document dont l'emplacement
    n'est plus proposé (date de clôture changée) garde le sien."""
    par_cle: dict[str, list[DocumentImport]] = {}
    for d in documents:
        par_cle.setdefault(cle_du_document(d), []).append(d)
    vides = _vides(champs, aujourd_hui)
    connus = {e.cle for e in vides}
    orphelins = [
        Emplacement(
            cle,
            cle.split(":")[0],
            docs[0].categorie,
            docs[0].exercice,
            CATEGORIES_DOCUMENTS.get(docs[0].categorie, "Document"),
            "Déposé plus tôt.",
            False,
        )
        for cle, docs in par_cle.items()
        if cle not in connus
    ]
    return [replace(e, documents=tuple(par_cle.get(e.cle, ()))) for e in [*vides, *orphelins]]


def _manquants_champs(section: Section, champs: Mapping[str, str]) -> list[str]:
    manquants = [c.libelle for c in section.champs if c.obligatoire and not champs.get(c.cle)]
    if section.cle == "fiscalite" and champs.get("regime_imposition") == "option_IR":
        if not champs.get("option_ir_debut"):
            manquants.append("Première année de l'option IR")
    if section.cle == "dirigeant":
        associes = lire_associes(champs.get("associes"))
        total = total_parts(associes)
        if any(a.pourcentage for a in associes) and total != 100:
            manquants.append(f"Parts des associés : {total.normalize():f} % sur 100 %")
    if section.cle == "reprise" and not (champs.get("date_creation") and champs.get("cloture")):
        manquants.append("Date de création et date de clôture (catégorie Entreprise)")
    return manquants


def etat_sections(
    fiche: FicheImport, documents: Sequence[DocumentImport], aujourd_hui: date
) -> list[EtatSection]:
    """Chaque catégorie : complète, ou ce qui lui manque (champs attendus et
    emplacements attendus vides)."""
    vides = [
        e for e in emplacements(fiche.champs, documents, aujourd_hui) if e.attendu and not e.rempli
    ]
    etats = []
    for section in SECTIONS:
        manquants = _manquants_champs(section, fiche.champs)
        manquants += [e.libelle for e in vides if e.section == section.cle]
        etats.append(EtatSection(section.cle, section.libelle, not manquants, tuple(manquants)))
    return etats


def statut_calcule(
    fiche: FicheImport, documents: Sequence[DocumentImport], aujourd_hui: date
) -> Statut:
    if not documents and set(fiche.champs) <= CHAMPS_DE_DEPART:
        return "a_importer"
    complete = all(e.complet for e in etat_sections(fiche, documents, aujourd_hui))
    lisibles = all(d.statut_traitement != "illisible" for d in documents)
    return "traitee" if complete and lisibles else "en_traitement"


POUR_CREER = (
    ("siren", "SIREN"),
    ("denomination", "Dénomination"),
    ("forme_juridique", "Forme juridique"),
    ("regime_imposition", "Imposition des bénéfices"),
    ("regime_tva", "Régime de TVA"),
    ("exercice_debut", "Début de l'exercice en cours"),
)


def manque_pour_creer(fiche: FicheImport) -> list[str]:
    """Ce qu'il faut pour ajouter le chauffeur au portefeuille ; le reste se
    complète ensuite."""
    return [libelle for cle, libelle in POUR_CREER if not fiche.champs.get(cle)]


def ligne_dossier(fiche: FicheImport) -> dict[str, str]:
    """La fiche en ligne d'import (AXE-809) : même validation, même création."""
    champs = fiche.champs
    contact = "".join(c for c in champs.get("contact_digifactory", "") if c.isdigit())
    return {
        "siren": champs.get("siren", ""),
        "nom": champs.get("denomination", ""),
        "forme_juridique": champs.get("forme_juridique", ""),
        "regime_imposition": champs.get("regime_imposition", ""),
        "regime_tva": champs.get("regime_tva", ""),
        "tva_recettes_regime": (
            "franchise" if champs.get("regime_tva") == "franchise" else "assujetti_taux_reduit"
        ),
        "exercice_debut": champs.get("exercice_debut", ""),
        "exercice_fin": champs.get("exercice_fin", ""),
        "option_ir_debut": champs.get("option_ir_debut", ""),
        "contact_digifactory": contact,
    }


def dossier_prevu(fiche: FicheImport) -> str:
    ligne = ligne_dossier(fiche)
    return str(identifiant(ligne["siren"], ligne["contact_digifactory"]))


# --- Contact Digifactory de la fiche (AXE-947) --------------------------------


@dataclass(frozen=True, slots=True)
class ContactDigifactory:
    contact_nr: str
    nom: str
    siren: str | None


@dataclass(frozen=True, slots=True)
class Correspondance:
    contact: ContactDigifactory
    raison: str  # « même SIREN » ou « même nom »


def _mots(texte: str) -> set[str]:
    ascii_ = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().upper()
    return {m for m in "".join(c if c.isalnum() else " " for c in ascii_).split() if len(m) > 1}


def contacts_correspondants(
    fiche: FicheImport, contacts: Iterable[ContactDigifactory]
) -> list[Correspondance]:
    """Comme la synchro : le même SIREN, ou un nom de contact qui contient la
    dénomination ou le nom et le prénom du chauffeur."""
    champs = fiche.champs
    siren = champs.get("siren")
    noms = [
        m
        for m in (_mots(champs.get("denomination", "")), _mots(f"{fiche.prenom} {fiche.nom}"))
        if m
    ]
    trouves = []
    for contact in contacts:
        if siren and contact.siren == siren:
            trouves.append(Correspondance(contact, "même SIREN"))
        elif any(nom <= _mots(contact.nom) for nom in noms):
            trouves.append(Correspondance(contact, "même nom"))
    return sorted(trouves, key=lambda c: (c.raison != "même SIREN", c.contact.nom))
