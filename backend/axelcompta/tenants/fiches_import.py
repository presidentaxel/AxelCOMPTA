"""Fiche d'import d'un chauffeur (AXE-941). Pur.

Pour reprendre un chauffeur, l'équipe remplit une fiche par catégorie
(entreprise, dirigeant, fiscalité, reprise comptable, banque, plateformes,
documents), comme la création d'entreprise chez Qonto. Le SIREN préremplit
l'entreprise et le dirigeant depuis l'INSEE et le RNE ; la personne qui
importe complète le reste et dépose les documents.

La fiche vit dans le portefeuille du gestionnaire qui l'a ouverte. Son
statut va de « à importer » à « traitée » ; elle reste modifiable tant
qu'elle n'est pas traitée. « Créer le chauffeur » ajoute le dossier dans ce
portefeuille, par le même chemin que l'import CSV (AXE-809).

Rien n'est lu automatiquement dans les documents (OCR : AXE-943).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, TenantId

from .import_dossiers import siren_valide
from .registres import FicheOfficielle

Statut = Literal["a_importer", "en_traitement", "traitee"]
STATUTS: tuple[Statut, ...] = ("a_importer", "en_traitement", "traitee")
TypeChamp = Literal[
    "texte",
    "long",
    "date",
    "siren",
    "email",
    "telephone",
    "choix",
    "multi",
    "montant",
    "annee",
    "jour_mois",
]
LONGUEUR_MAX = 2_000


class FicheTraitee(SaisieInvalide):
    """Une fiche traitée ne se modifie plus : la repasser en traitement."""


@dataclass(frozen=True, slots=True)
class Champ:
    cle: str
    libelle: str
    type: TypeChamp = "texte"
    obligatoire: bool = False
    choix: tuple[tuple[str, str], ...] = ()
    aide: str = ""


@dataclass(frozen=True, slots=True)
class Section:
    cle: str
    libelle: str
    description: str
    champs: tuple[Champ, ...] = ()


FORMES = (("SASU", "SASU"), ("SAS", "SAS"), ("EURL", "EURL"), ("SARL", "SARL"), ("EI", "EI"))
IMPOSITIONS = (("IS", "IS"), ("option_IR", "IR sur option (5 ans)"), ("IR", "IR"))
REGIMES_TVA = (
    ("franchise", "Franchise en base"),
    ("reel_simplifie", "Réel simplifié"),
    ("reel_normal", "Réel normal"),
)
VEHICULES = (("aucun", "Aucun"), ("achat", "Acheté"), ("loa", "LOA"), ("lld", "LLD"))
PLATEFORMES = (
    ("uber", "Uber"),
    ("bolt", "Bolt"),
    ("heetch", "Heetch"),
    ("allocab", "Allocab"),
    ("freenow", "Free Now"),
    ("autre", "Autre"),
)

SECTIONS: tuple[Section, ...] = (
    Section(
        "entreprise",
        "Entreprise",
        "Préremplie par l'INSEE et le RNE avec le SIREN.",
        (
            Champ("siren", "SIREN", "siren", True),
            Champ("denomination", "Dénomination", obligatoire=True),
            Champ("forme_juridique", "Forme juridique", "choix", True, FORMES),
            Champ("siege", "Adresse du siège", obligatoire=True),
            Champ("capital", "Capital (€)", "montant"),
            Champ("code_naf", "Code NAF"),
            Champ("date_creation", "Date de création", "date", True),
            Champ("cloture", "Date de clôture (JJ/MM)", "jour_mois", True),
            Champ("premiere_cloture", "Date de première clôture", "date"),
        ),
    ),
    Section(
        "dirigeant",
        "Dirigeant et contact",
        "Pour inviter le chauffeur dans son app, et relier ses comptes Rollee.",
        (
            Champ("nom", "Nom", obligatoire=True),
            Champ("prenom", "Prénom", obligatoire=True),
            Champ("email", "E-mail", "email", True),
            Champ("telephone", "Téléphone", "telephone"),
            Champ(
                "associes",
                "Associés et parts",
                "long",
                aide="Un associé par ligne : nom, % du capital.",
            ),
        ),
    ),
    Section(
        "fiscalite",
        "Fiscalité",
        "Le régime décide des écritures : à vérifier sur la dernière liasse.",
        (
            Champ("regime_imposition", "Imposition des bénéfices", "choix", True, IMPOSITIONS),
            Champ("option_ir_debut", "Première année de l'option IR", "annee"),
            Champ("regime_tva", "Régime de TVA", "choix", True, REGIMES_TVA),
            Champ("numero_tva", "Numéro de TVA intracommunautaire"),
            Champ("exercice_debut", "Début de l'exercice en cours", "date", True),
            Champ("exercice_fin", "Fin de l'exercice en cours", "date"),
        ),
    ),
    Section(
        "reprise",
        "Reprise comptable",
        "Les exercices à reprendre et leurs pièces, d'après la création et la clôture.",
        (
            Champ("deficits", "Déficits reportables (€)", "montant"),
            Champ("credit_tva", "Crédit de TVA à reporter (€)", "montant"),
            Champ("vehicule", "Véhicule", "choix", choix=VEHICULES),
            Champ(
                "vehicule_detail",
                "Véhicule : détail",
                "long",
                aide="Date et prix d'achat, ou contrat de LOA/LLD.",
            ),
            Champ(
                "emprunts", "Emprunts en cours", "long", aide="Banque, capital restant, échéances."
            ),
            Champ(
                "ancien_comptable",
                "Ancien expert-comptable",
                aide="Cabinet et contact, s'il y en a un.",
            ),
        ),
    ),
    Section(
        "banque",
        "Banque",
        "Le contact Digifactory (Bridge) qui remonte les comptes du chauffeur.",
        (
            Champ("contact_digifactory", "Numéro de contact Digifactory", obligatoire=True),
            Champ("debut_historique", "Début de l'historique bancaire", "date"),
            Champ(
                "comptes_bancaires",
                "Comptes bancaires",
                "long",
                aide="Banque et usage : pro, perso.",
            ),
        ),
    ),
    Section(
        "plateformes",
        "Plateformes",
        "Les plateformes du chauffeur et ses comptes Rollee (il peut en avoir plusieurs).",
        (
            Champ("plateformes", "Plateformes utilisées", "multi", True, PLATEFORMES),
            Champ(
                "comptes_rollee",
                "Comptes Rollee",
                "long",
                aide="Un compte par ligne : plateforme, nom ou e-mail.",
            ),
        ),
    ),
    Section(
        "documents",
        "Documents administratifs",
        "Kbis, statuts, RIB. La lettre de l'ancien comptable est facultative.",
    ),
)
_CHAMPS: dict[str, Champ] = {c.cle: c for s in SECTIONS for c in s.champs}

CATEGORIES_DOCUMENTS: dict[str, str] = {
    "liasse": "Liasse fiscale",
    "fec": "FEC",
    "balance": "Balance",
    "grand_livre": "Grand livre",
    "kbis": "Kbis",
    "statuts": "Statuts",
    "rib": "RIB",
    "lettre_comptable": "Lettre de l'ancien expert-comptable",
    "releve_bancaire": "Relevé bancaire",
    "autre": "Autre document",
}
DOCUMENTS_ADMINISTRATIFS = ("kbis", "statuts", "rib")  # attendus ; la lettre est facultative


@dataclass(frozen=True, slots=True)
class DocumentImport:
    """Un fichier déposé sur une fiche. Le contenu est gardé à part."""

    id: str
    fiche_id: str
    tenant_id: TenantId
    categorie: str
    exercice: int | None  # année de clôture de l'exercice concerné
    nom_fichier: str
    type_mime: str
    taille: int
    empreinte: str  # SHA-256 du contenu
    depose_par: str
    depose_le: datetime


@dataclass(frozen=True, slots=True)
class FicheImport:
    id: str
    tenant_id: TenantId
    nom: str
    prenom: str
    cree_par: str
    cree_le: datetime
    statut: Statut = "a_importer"
    champs: Mapping[str, str] = field(default_factory=dict)
    registre: FicheOfficielle | None = None
    dossier_id: DossierId | None = None
    maj_par: str = ""
    maj_le: datetime | None = None


def nouvelle_fiche(
    id_: str, tenant_id: TenantId, nom: str, prenom: str, siren: str, par: str, le: datetime
) -> FicheImport:
    nom, prenom = " ".join(nom.split()), " ".join(prenom.split())
    if not nom and not prenom:
        raise SaisieInvalide("Indiquez au moins le nom ou le prénom du chauffeur.")
    champs = {k: v for k, v in valider({"nom": nom, "prenom": prenom, "siren": siren}).items() if v}
    return FicheImport(id_, tenant_id, nom, prenom, par, le, champs=champs, maj_par=par, maj_le=le)


def _montant(texte: str, libelle: str) -> str:
    propre = texte.replace(" ", "").replace(" ", "").replace("€", "").replace(",", ".")
    try:
        return str(Decimal(propre).quantize(Decimal("0.01")))
    except InvalidOperation as exc:
        raise SaisieInvalide(f"{libelle} : un montant en euros, par exemple 1 250,00.") from exc


def _jour_mois(texte: str, libelle: str) -> str:
    trouve = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})", texte)
    if trouve is None or not (1 <= int(trouve[2]) <= 12 and 1 <= int(trouve[1]) <= 31):
        raise SaisieInvalide(f"{libelle} : jour et mois, par exemple 31/12.")
    return f"{int(trouve[1]):02d}/{int(trouve[2]):02d}"


def _date(texte: str, libelle: str) -> str:
    try:
        return date.fromisoformat(texte).isoformat()
    except ValueError as exc:
        raise SaisieInvalide(f"{libelle} : une date (AAAA-MM-JJ).") from exc


def _choix(champ: Champ, texte: str) -> str:
    permis = {cle for cle, _ in champ.choix}
    valeurs = (
        [v.strip() for v in texte.split(",") if v.strip()] if champ.type == "multi" else [texte]
    )
    if not set(valeurs) <= permis:
        raise SaisieInvalide(f"{champ.libelle} : valeur inconnue.")
    return ",".join(dict.fromkeys(valeurs))


def _valeur(champ: Champ, texte: str) -> str:
    """La valeur rangée, ou `SaisieInvalide` avec un message pour l'écran."""
    if champ.type == "siren":
        siren = texte.replace(" ", "")
        if not siren_valide(siren):
            raise SaisieInvalide("SIREN invalide : neuf chiffres.")
        return siren
    if champ.type == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", texte):
        raise SaisieInvalide("E-mail invalide.")
    if champ.type == "telephone" and len(re.sub(r"\D", "", texte)) < 9:
        raise SaisieInvalide("Téléphone invalide.")
    if champ.type == "annee" and not re.fullmatch(r"(19|20)\d\d", texte):
        raise SaisieInvalide(f"{champ.libelle} : une année, par exemple 2025.")
    if champ.type in ("choix", "multi"):
        return _choix(champ, texte)
    if champ.type == "montant":
        return _montant(texte, champ.libelle)
    if champ.type == "date":
        return _date(texte, champ.libelle)
    if champ.type == "jour_mois":
        return _jour_mois(texte, champ.libelle)
    return texte


def valider(saisie: Mapping[str, str]) -> dict[str, str]:
    """Chaque champ saisi, rangé ; une valeur vide efface le champ (« »)."""
    rangees: dict[str, str] = {}
    for cle, brut in saisie.items():
        champ = _CHAMPS.get(cle)
        if champ is None:
            raise SaisieInvalide(f"Champ inconnu : {cle}.")
        texte = " ".join(brut.split()) if champ.type != "long" else brut.strip()
        if len(texte) > LONGUEUR_MAX:
            raise SaisieInvalide(f"{champ.libelle} : {LONGUEUR_MAX} caractères au plus.")
        rangees[cle] = _valeur(champ, texte) if texte else ""
    return rangees


def modifier(fiche: FicheImport, saisie: Mapping[str, str], par: str, le: datetime) -> FicheImport:
    """Les champs saisis remplacent les anciens. Une fiche à importer passe
    en traitement dès la première saisie."""
    if fiche.statut == "traitee":
        raise FicheTraitee("Cette fiche est traitée : repassez-la en traitement pour la modifier.")
    champs = {**fiche.champs, **valider(saisie)}
    champs = {k: v for k, v in champs.items() if v}
    statut: Statut = "en_traitement" if fiche.statut == "a_importer" else fiche.statut
    nom = champs.get("nom", fiche.nom)
    prenom = champs.get("prenom", fiche.prenom)
    return replace(
        fiche, champs=champs, statut=statut, nom=nom, prenom=prenom, maj_par=par, maj_le=le
    )


def changer_statut(fiche: FicheImport, statut: str, par: str, le: datetime) -> FicheImport:
    if statut not in STATUTS:
        raise SaisieInvalide(f"Statut inconnu : {statut}.")
    return replace(fiche, statut=statut, maj_par=par, maj_le=le)


def _euros(centimes: int) -> str:
    return f"{centimes // 100}.{centimes % 100:02d}"


def depuis_registre(officielle: FicheOfficielle) -> dict[str, str]:
    """Ce que les registres remplissent ; rien pour ce qu'ils ne disent pas."""
    valeurs = {
        "siren": officielle.siren,
        "denomination": officielle.denomination or "",
        "forme_juridique": officielle.forme_juridique or "",
        "siege": officielle.siege.sur_une_ligne() if officielle.siege else "",
        "capital": _euros(officielle.capital_cts) if officielle.capital_cts is not None else "",
        "code_naf": officielle.code_naf or "",
        "date_creation": officielle.date_creation.isoformat() if officielle.date_creation else "",
        "cloture": officielle.cloture or "",
        "premiere_cloture": (
            officielle.premiere_cloture.isoformat() if officielle.premiere_cloture else ""
        ),
    }
    if officielle.personnes:
        valeurs["nom"] = officielle.personnes[0].nom
        valeurs["prenom"] = officielle.personnes[0].prenoms.split(" ")[0]
    if valeurs["forme_juridique"] not in {cle for cle, _ in FORMES}:
        valeurs["forme_juridique"] = ""
    return {k: v for k, v in valeurs.items() if v}


def preremplir(
    fiche: FicheImport, officielle: FicheOfficielle, par: str, le: datetime
) -> FicheImport:
    """Les registres remplissent les champs vides ; une saisie n'est jamais
    écrasée. La lecture est gardée avec la fiche."""
    if fiche.statut == "traitee":
        raise FicheTraitee("Cette fiche est traitée : repassez-la en traitement pour la modifier.")
    lus = depuis_registre(officielle)
    champs = {**lus, **fiche.champs}
    return replace(
        fiche,
        champs=champs,
        registre=officielle,
        nom=champs.get("nom", fiche.nom),
        prenom=champs.get("prenom", fiche.prenom),
        maj_par=par,
        maj_le=le,
    )


def document_import(
    id_: str,
    fiche: FicheImport,
    categorie: str,
    exercice: int | None,
    nom_fichier: str,
    type_mime: str,
    contenu: bytes,
    par: str,
    le: datetime,
) -> DocumentImport:
    """Un document déposé sur la fiche, avec l'empreinte de son contenu."""
    if fiche.statut == "traitee":
        raise FicheTraitee("Cette fiche est traitée : repassez-la en traitement pour la modifier.")
    if categorie not in CATEGORIES_DOCUMENTS:
        raise SaisieInvalide(f"Catégorie de document inconnue : {categorie}.")
    if exercice is not None and not 2000 <= exercice <= 2100:
        raise SaisieInvalide("Exercice : l'année de clôture, par exemple 2025.")
    return DocumentImport(
        id=id_,
        fiche_id=fiche.id,
        tenant_id=fiche.tenant_id,
        categorie=categorie,
        exercice=exercice,
        nom_fichier=nom_fichier[:200] or "document",
        type_mime=type_mime or "application/octet-stream",
        taille=len(contenu),
        empreinte=hashlib.sha256(contenu).hexdigest(),
        depose_par=par,
        depose_le=le,
    )
