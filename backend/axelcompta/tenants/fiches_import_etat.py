"""Ce qui manque à une fiche d'import, ses emplacements de documents et son
statut (AXE-941, AXE-947). Pur.

**Emplacements** : un par document attendu, avec ce que c'est et pourquoi.
Pour un exercice clos depuis 2024 : liasse et FEC (ou balance et grand
livre sans FEC) ; seul le dernier exercice clos est indispensable, il donne
le report à nouveau. AXE-970 : tout exercice plus ancien s'ajoute à la main
(« Ajouter un exercice », depuis 2000, même avec des trous), ou apparaît dès
qu'un document y est rangé ; les autres pièces d'un dossier de clôture
(comptes annuels, déclarations, accusés, paiements, pièces, archives) ont
leur emplacement dès qu'un document y est classé. En banque : les relevés
des mois que Digifactory ne couvre pas, et le RIB. Documents administratifs : Kbis, statuts, et la
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
    ANNEE_MIN_ARCHIVE,
    CATEGORIES_DOCUMENTS,
    SECTIONS,
    DocumentImport,
    FicheImport,
    Section,
    Statut,
)
from .fiches_import_calculs import bornes, bornes_de, date_limite_liasse
from .fiches_import_listes import lire_associes, total_parts
from .import_dossiers import identifiant, rapport
from .models import Dossier

ANNEE_MIN_REPRISE = 2024
SECTION_PAR_CATEGORIE = {
    "liasse": "reprise",
    "fec": "reprise",
    "balance": "reprise",
    "grand_livre": "reprise",
    "comptes_annuels": "reprise",
    "declaration_tva": "reprise",
    "declaration_is": "reprise",
    "accuse_reception": "reprise",
    "paiement_impot": "reprise",
    "piece": "reprise",
    "archive": "reprise",
    "releve_bancaire": "banque",
    "rib": "banque",
    "kbis": "documents",
    "statuts": "documents",
    "lettre_comptable": "documents",
    "autre": "documents",
}
CHAMPS_DE_DEPART = frozenset({"nom", "prenom"})
# AXE-970 : le reste d'un dossier de clôture, proposé seulement quand un
# document y est classé (sinon chaque exercice aurait douze cartes vides).
EXPLICATIONS_EXERCICE = {
    "comptes_annuels": "Bilan, compte de résultat, annexe.",
    "declaration_tva": "CA3, CA12 (3517-S) et leurs synthèses.",
    "declaration_is": "Relevés d'acompte et de solde (2571, 2572).",
    "accuse_reception": "Accusés de dépôt des déclarations.",
    "paiement_impot": "Ordres de paiement et avis de prélèvement.",
    "piece": "Factures, reçus, encaissements.",
    "archive": "Gardée intacte : chaque fichier qu'elle contient est rangé à part.",
    "releve_bancaire": "Relevés des comptes sur l'exercice.",
    "autre": "Tout autre document de l'exercice.",
}


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


RoleExercice = Literal["en_cours", "a_declarer", "source", "anterieur"]


@dataclass(frozen=True, slots=True)
class Exercice:
    """AXE-950 : « à déclarer » par nous tant que la date limite de sa liasse
    n'est pas passée (ou s'il n'a jamais été déposé) ; « source » : le
    dernier exercice déposé, dont la liasse donne le report à nouveau."""

    debut: date
    fin: date
    role: RoleExercice
    echeance: date | None  # date limite de dépôt de sa liasse
    en_retard: bool = False

    @property
    def annee(self) -> int:
        return self.fin.year

    @property
    def etat(self) -> Literal["clos", "en_cours"]:
        return "en_cours" if self.role == "en_cours" else "clos"


@dataclass(frozen=True, slots=True)
class EtatSection:
    cle: str
    libelle: str
    complet: bool
    manquants: tuple[str, ...]


def annees_en_retard(champs: Mapping[str, str]) -> set[int]:
    return {int(a) for a in champs.get("en_retard", "").split(",") if a.isdigit()}


def annees_ajoutees(champs: Mapping[str, str]) -> set[int]:
    """AXE-970 : les exercices ajoutés à la main (« Ajouter un exercice »)."""
    return {
        int(a)
        for a in champs.get("exercices_ajoutes", "").split(",")
        if a.isdigit() and int(a) >= ANNEE_MIN_ARCHIVE
    }


def _roles(clos: list[date], aujourd_hui: date, retard: set[int]) -> dict[date, RoleExercice]:
    """En remontant depuis le dernier exercice clos : à déclarer tant que la
    date limite n'est pas passée ou qu'il n'a pas été déposé ; le premier
    exercice déposé est la source du report à nouveau."""
    roles: dict[date, RoleExercice] = {}
    for fin in reversed(clos):
        if aujourd_hui <= date_limite_liasse(fin) or fin.year in retard:
            roles[fin] = "a_declarer"
            continue
        roles[fin] = "source"
        break
    return roles


def exercices(
    champs: Mapping[str, str],
    aujourd_hui: date,
    documents: Iterable[DocumentImport] = (),
) -> list[Exercice]:
    """L'exercice en cours, ceux à déclarer par nous, la source du report à
    nouveau, les exercices antérieurs déposés depuis 2024, et (AXE-970) tout
    exercice ajouté à la main ou qui a déjà un document, du plus ancien au
    plus récent."""
    tous = bornes(champs, aujourd_hui)
    retard = annees_en_retard(champs)
    voulus = annees_ajoutees(champs) | {
        d.exercice for d in documents if d.exercice and d.exercice >= ANNEE_MIN_ARCHIVE
    }
    roles = _roles([fin for _d, fin in tous if fin < aujourd_hui], aujourd_hui, retard)
    resultat = []
    for debut, fin in tous:
        role: RoleExercice = "en_cours" if fin >= aujourd_hui else roles.get(fin, "anterieur")
        if role == "anterieur" and fin.year < ANNEE_MIN_REPRISE and fin.year not in voulus:
            continue
        echeance = None if role == "en_cours" else date_limite_liasse(fin)
        resultat.append(Exercice(debut, fin, role, echeance, fin.year in retard))
    connues = {e.annee for e in resultat}
    for annee in sorted(voulus - connues):
        # Avant la création connue (ou date de création inconnue) : bornes
        # déduites de la date de clôture, 31/12 par défaut.
        debut, fin = bornes_de(champs, annee)
        if fin >= aujourd_hui:
            continue
        resultat.append(Exercice(debut, fin, "anterieur", date_limite_liasse(fin)))
    return sorted(resultat, key=lambda e: e.fin)


def cle_du_document(document: DocumentImport) -> str:
    """Son emplacement ; pour un document d'avant AXE-947, celui de sa catégorie."""
    if document.emplacement:
        return document.emplacement
    section = SECTION_PAR_CATEGORIE.get(document.categorie, "documents")
    annee = f":{document.exercice}" if section == "reprise" and document.exercice else ""
    return f"{section}:{document.categorie}{annee}"


def _jj(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _emplacements_exercice(e: Exercice, suivant: Exercice | None) -> list[Emplacement]:
    cle, quand = f"reprise:{{}}:{e.annee}", f"de l'exercice clos le {_jj(e.fin)}"
    if e.role == "a_declarer":
        echeance = _jj(e.echeance) if e.echeance else ""
        return [
            Emplacement(
                cle.format("fec"),
                "reprise",
                "fec",
                e.annee,
                f"Écritures {e.annee} déjà saisies",
                f"Exercice à déclarer par nous (liasse avant le {echeance}) : FEC ou grand "
                "livre, seulement si l'ancien comptable a commencé.",
                False,
            ),
        ]
    source = e.role == "source"
    pour = (
        f"donne le report à nouveau pour déclarer l'exercice {suivant.annee}"
        if source and suivant
        else "si vous l'avez"
    )
    return [
        Emplacement(
            cle.format("liasse"),
            "reprise",
            "liasse",
            e.annee,
            f"Liasse fiscale {e.annee}",
            f"2033 ou 2065 {quand}, déjà déposée ; {pour}.",
            source,
        ),
        Emplacement(
            cle.format("fec"),
            "reprise",
            "fec",
            e.annee,
            f"FEC {e.annee}",
            f"Fichier des écritures {quand}, à demander à l'ancien comptable.",
            source,
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


def _reprise(
    champs: Mapping[str, str], aujourd_hui: date, documents: Sequence[DocumentImport] = ()
) -> list[Emplacement]:
    liste = exercices(champs, aujourd_hui, documents)
    emplacements = []
    for i, e in enumerate(liste):
        if e.role != "en_cours":
            emplacements += _emplacements_exercice(e, liste[i + 1] if i + 1 < len(liste) else None)
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


def debut_a_couvrir(champs: Mapping[str, str], aujourd_hui: date) -> date | None:
    """AXE-971 : depuis quand la banque doit être complète. Le début du plus
    ancien exercice que nous tenons : à déclarer par nous, ou en cours. Sans
    dates d'exercice, le début de l'exercice en cours saisi."""
    tenus = [
        e.debut for e in exercices(champs, aujourd_hui) if e.role in ("a_declarer", "en_cours")
    ]
    if tenus:
        return min(tenus)
    debut = champs.get("exercice_debut")
    return date.fromisoformat(debut) if debut else None


def _releves(champs: Mapping[str, str], aujourd_hui: date) -> Emplacement:
    """AXE-971 : les relevés sont obligatoires tant que la banque connectée ne
    couvre pas tout depuis `debut_a_couvrir` ; facultatifs seulement quand
    Digifactory remonte toute la période."""
    cle, libelle = "banque:releve_bancaire", "Relevés bancaires"
    debut = debut_a_couvrir(champs, aujourd_hui)
    depuis = f"du {_jj(debut)} à aujourd'hui" if debut else "de l'exercice en cours"
    historique = champs.get("debut_historique")
    if not champs.get("contact_digifactory"):
        explication = (
            f"La banque n'est pas encore connectée à Digifactory : relevés {depuis}, "
            "en PDF, QIF ou CSV."
        )
        return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, True)
    if not historique:
        explication = (
            f"L'historique Digifactory n'est pas encore connu : relevés {depuis}, "
            "en PDF, QIF ou CSV, sauf si Digifactory remonte tout."
        )
        return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, True)
    premier = date.fromisoformat(historique)
    if debut and premier > debut:
        veille = premier - timedelta(days=1)
        explication = (
            f"Du {_jj(debut)} au {_jj(veille)} : avant l'historique Digifactory, "
            "indispensable pour tenir les comptes. En PDF, QIF ou CSV."
        )
        return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, True)
    explication = (
        f"Digifactory remonte tout depuis le {_jj(premier)} : seulement si des mois manquent."
    )
    return Emplacement(cle, "banque", "releve_bancaire", None, libelle, explication, False)


def _vides(
    champs: Mapping[str, str], aujourd_hui: date, documents: Sequence[DocumentImport] = ()
) -> list[Emplacement]:
    return [
        *_reprise(champs, aujourd_hui, documents),
        _releves(champs, aujourd_hui),
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
    vides = _vides(champs, aujourd_hui, documents)
    connus = {e.cle for e in vides}
    orphelins = [
        _emplacement_classe(cle, docs[0]) for cle, docs in par_cle.items() if cle not in connus
    ]
    return [replace(e, documents=tuple(par_cle.get(e.cle, ()))) for e in [*vides, *orphelins]]


def _emplacement_classe(cle: str, document: DocumentImport) -> Emplacement:
    """L'emplacement d'un document classé hors des cartes proposées : une
    autre pièce de l'exercice (AXE-970), ou une carte qui n'est plus proposée
    (date de clôture changée)."""
    libelle = CATEGORIES_DOCUMENTS.get(document.categorie, "Document")
    section = cle.split(":")[0]
    explication = (
        EXPLICATIONS_EXERCICE.get(document.categorie, "Déposé plus tôt.")
        if section == "reprise"
        else "Déposé plus tôt."
    )
    if document.exercice and section == "reprise":
        libelle = f"{libelle} {document.exercice}"
    return Emplacement(
        cle, section, document.categorie, document.exercice, libelle, explication, False
    )


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
    if fiche.statut == "ignore":
        return "ignore"
    if not documents and set(fiche.champs) <= CHAMPS_DE_DEPART:
        return "a_importer"
    complete = all(e.complet for e in etat_sections(fiche, documents, aujourd_hui))
    lisibles = all(d.statut_traitement != "illisible" for d in documents)
    return "traitee" if complete and lisibles else "en_traitement"


# Même point de départ qu'un contact Digifactory : l'imposition et la TVA
# se complètent ensuite, le dossier existe déjà.
_REGIME_DEFAUT = "IS"
_TVA_DEFAUT = "reel_normal"
A_CONFIRMER_IMPOSITION = "imposition"

POUR_CREER = (
    ("siren", "SIREN"),
    ("denomination", "Dénomination"),
    ("forme_juridique", "Forme juridique"),
    ("exercice_debut", "Début de l'exercice en cours"),
)


def manque_pour_creer(fiche: FicheImport) -> list[str]:
    """Ce qu'il faut pour ajouter le chauffeur au portefeuille ; le reste se
    complète ensuite."""
    return [libelle for cle, libelle in POUR_CREER if not fiche.champs.get(cle)]


def _regime_suppose(fiche: FicheImport) -> bool:
    return not fiche.champs.get("regime_imposition") or not fiche.champs.get("regime_tva")


def ligne_dossier(fiche: FicheImport) -> dict[str, str]:
    """La fiche en ligne d'import (AXE-809) : même validation, même création.
    Sans imposition ni TVA, le dossier part à l'IS au réel normal, comme un
    contact Digifactory, et cette hypothèse reste à confirmer."""
    champs = fiche.champs
    contact = "".join(c for c in champs.get("contact_digifactory", "") if c.isdigit())
    regime_tva = champs.get("regime_tva") or _TVA_DEFAUT
    return {
        "siren": champs.get("siren", ""),
        "nom": champs.get("denomination", ""),
        "forme_juridique": champs.get("forme_juridique", ""),
        "regime_imposition": champs.get("regime_imposition") or _REGIME_DEFAUT,
        "regime_tva": regime_tva,
        "tva_recettes_regime": (
            "franchise" if regime_tva == "franchise" else "assujetti_taux_reduit"
        ),
        "exercice_debut": champs.get("exercice_debut", ""),
        "exercice_fin": champs.get("exercice_fin", ""),
        "option_ir_debut": champs.get("option_ir_debut", ""),
        "contact_digifactory": contact,
    }


def relier_au_portefeuille(
    fiche: FicheImport, dossiers: Sequence[Dossier]
) -> tuple[FicheImport, Dossier | None, tuple[str, ...]]:
    """La fiche reliée au dossier du portefeuille, le dossier à créer, et
    ce qui empêche encore de le créer.

    Une fiche annulée reste seule. Le même SIREN, ou le même identifiant,
    relie sans créer un second dossier. Une fiche incomplète sans dossier
    déjà là reste dans Imports. Rien n'est écrit.
    """
    if fiche.annulee_le is not None or fiche.statut == "ignore":
        return fiche, None, ()
    presents = [d for d in dossiers if d.retire_le is None]
    deja = {d.id for d in presents}
    if fiche.dossier_id is not None and fiche.dossier_id in deja:
        return fiche, None, ()
    siren = fiche.champs.get("siren")
    meme = next((d for d in presents if siren and d.siren == siren), None)
    if meme is not None:
        return replace(fiche, dossier_id=meme.id), None, ()
    manque = manque_pour_creer(fiche)
    if manque:
        return fiche, None, tuple(manque)
    ligne = ligne_dossier(fiche)
    (resultat,) = rapport(fiche.tenant_id, [ligne], deja).lignes
    if resultat.dossier is not None:
        dossier = resultat.dossier
        if _regime_suppose(fiche):
            dossier = replace(dossier, a_confirmer=(*dossier.a_confirmer, A_CONFIRMER_IMPOSITION))
        return replace(fiche, dossier_id=dossier.id), dossier, ()
    prevu = identifiant(ligne["siren"], ligne["contact_digifactory"])
    if prevu in deja:
        return replace(fiche, dossier_id=prevu), None, ()
    return fiche, None, resultat.erreurs


def relier_toutes(
    fiches: Sequence[FicheImport], dossiers: Sequence[Dossier]
) -> tuple[list[FicheImport], list[Dossier]]:
    """AXE-974 : chaque fiche active complète a son dossier. Les fiches dont
    le lien change, et les dossiers à créer (un seul par identifiant).
    Rien n'est écrit : la création revient au worker (rôle propriétaire)."""
    existants = list(dossiers)
    changees: list[FicheImport] = []
    a_creer: list[Dossier] = []
    for fiche in fiches:
        reliee, dossier, _erreurs = relier_au_portefeuille(fiche, existants)
        if dossier is not None:
            a_creer.append(dossier)
            existants.append(dossier)
        if reliee.dossier_id != fiche.dossier_id:
            changees.append(reliee)
    return changees, a_creer


# AXE-975 : ce qu'il faut vraiment lire pour reprendre un dossier. Les
# pièces, accusés, paiements et déclarations sont gardés, pas à lire.
CATEGORIES_A_LIRE = frozenset(
    {"liasse", "fec", "balance", "grand_livre", "comptes_annuels", "releve_bancaire"}
)
ROLES_A_LIRE = frozenset({"source", "a_declarer", "en_cours"})


def documents_a_lire(
    champs: Mapping[str, str], documents: Sequence[DocumentImport], aujourd_hui: date
) -> list[DocumentImport]:
    """Les documents qui attendent une lecture utile à la reprise : ceux des
    exercices qui donnent le report à nouveau ou que nous déclarons (et les
    relevés), dans les catégories qui portent des chiffres. Un document
    illisible compte toujours : il faut le remplacer. L'impression PDF d'un
    FEC ne compte pas : le FEC lui-même se lit."""
    utiles = {e.annee for e in exercices(champs, aujourd_hui, documents) if e.role in ROLES_A_LIRE}
    retenus = []
    for d in documents:
        if d.statut_traitement == "traite":
            continue
        if d.statut_traitement == "illisible":
            retenus.append(d)
            continue
        impression = (d.donnees or {}).get("type") == "impression_fec"
        if d.categorie not in CATEGORIES_A_LIRE or impression:
            continue
        if d.exercice is None or d.exercice in utiles:
            retenus.append(d)
    return retenus


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
