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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, TenantId

from .fiches_import_calculs import appliquer_deductions
from .fiches_import_listes import (
    FONCTIONS,
    associes_du_registre,
    ranger_associes,
    ranger_comptes_rollee,
)
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
    "siret",
    "associes",
    "rollee",
    "annees",
]
LONGUEUR_MAX = 2_000


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
            Champ("siren", "SIREN ou SIRET", "siren", True),
            Champ("siret", "SIRET du siège", "siret"),
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
                "Associés",
                "associes",
                choix=tuple(FONCTIONS.items()),
                aide="Fonction et part du capital de chacun.",
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
            # AXE-950 : exercices dont la date limite est passée mais dont la
            # liasse n'a jamais été déposée. Rendu sur chaque exercice.
            Champ("en_retard", "Exercices non déposés (en retard)", "annees"),
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
            Champ("comptes_rollee", "Comptes Rollee retenus", "rollee"),
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
StatutDocument = Literal["a_traiter", "traite", "illisible"]


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
    # AXE-947 : l'emplacement où il a été déposé (« reprise:liasse:2025 »),
    # et ce qui en a été tiré : « traite » (lu automatiquement), « a_traiter »
    # (à lire, OCR : AXE-943) ou « illisible », avec un résumé.
    emplacement: str = ""
    statut_traitement: StatutDocument = "a_traiter"
    resume: str = ""


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
    annulee_le: datetime | None = None  # AXE-947 : sortie de la liste
    annulee_par: str = ""


def nouvelle_fiche(
    id_: str, tenant_id: TenantId, nom: str, prenom: str, siren: str, par: str, le: datetime
) -> FicheImport:
    nom, prenom = " ".join(nom.split()), " ".join(prenom.split())
    if not nom and not prenom:
        raise SaisieInvalide("Indiquez au moins le nom ou le prénom du chauffeur.")
    champs = {k: v for k, v in valider({"nom": nom, "prenom": prenom, "siren": siren}).items() if v}
    champs = appliquer_deductions({}, champs, le.date())
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


def _luhn(chiffres: str) -> bool:
    total = 0
    for rang, chiffre in enumerate(int(c) for c in reversed(chiffres)):
        double = chiffre * 2 if rang % 2 == 1 else chiffre
        total += double - 9 if double > 9 else double
    return total % 10 == 0


def _identifiant(champ: Champ, texte: str) -> str:
    """SIREN (9 chiffres) ; le champ « SIREN ou SIRET » accepte aussi un
    SIRET (14), dont `valider` tire le SIREN."""
    chiffres = re.sub(r"[\s.]", "", texte)
    if len(chiffres) == 14 and chiffres.isdigit() and siren_valide(chiffres[:9]):
        if _luhn(chiffres) or chiffres.startswith("356000000"):  # La Poste : hors Luhn
            return chiffres
        raise SaisieInvalide("SIRET invalide : la clé de contrôle ne correspond pas.")
    if champ.type == "siren" and siren_valide(chiffres):
        return chiffres
    attendu = (
        "neuf chiffres (SIREN) ou quatorze (SIRET)"
        if champ.type == "siren"
        else "quatorze chiffres"
    )
    raise SaisieInvalide(f"{champ.libelle} invalide : {attendu}.")


def _annees(texte: str, libelle: str) -> str:
    annees = [a.strip() for a in texte.split(",") if a.strip()]
    if not all(re.fullmatch(r"(19|20)\d\d", a) for a in annees):
        raise SaisieInvalide(f"{libelle} : des années, par exemple 2025.")
    return ",".join(sorted(set(annees)))


def _controle(motif: str, message: str) -> Callable[[Champ, str], str]:
    def ranger(champ: Champ, texte: str) -> str:
        if not re.fullmatch(motif, texte):
            raise SaisieInvalide(message.format(libelle=champ.libelle))
        return texte

    return ranger


_RANGEMENTS: dict[str, Callable[[Champ, str], str]] = {
    "siren": _identifiant,
    "siret": _identifiant,
    "associes": lambda _c, texte: ranger_associes(texte),
    "rollee": lambda _c, texte: ranger_comptes_rollee(texte),
    "email": _controle(r"[^@\s]+@[^@\s]+\.[^@\s]+", "E-mail invalide."),
    "telephone": _controle(r"[+\d][\d\s.()-]{8,}", "Téléphone invalide."),
    "annee": _controle(r"(19|20)\d\d", "{libelle} : une année, par exemple 2025."),
    "choix": _choix,
    "multi": _choix,
    "montant": lambda c, texte: _montant(texte, c.libelle),
    "date": lambda c, texte: _date(texte, c.libelle),
    "jour_mois": lambda c, texte: _jour_mois(texte, c.libelle),
    "annees": lambda c, texte: _annees(texte, c.libelle),
}


def _valeur(champ: Champ, texte: str) -> str:
    """La valeur rangée, ou `SaisieInvalide` avec un message pour l'écran."""
    ranger = _RANGEMENTS.get(champ.type)
    return ranger(champ, texte) if ranger else texte


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
    siren = rangees.get("siren", "")
    if len(siren) == 14:  # un SIRET saisi dans « SIREN ou SIRET »
        rangees["siren"], rangees["siret"] = siren[:9], siren
    return rangees


def modifier(fiche: FicheImport, saisie: Mapping[str, str], par: str, le: datetime) -> FicheImport:
    """Les champs saisis remplacent les anciens ; ce qui s'en déduit (TVA,
    exercice en cours) suit."""
    champs = {**fiche.champs, **valider(saisie)}
    champs = {k: v for k, v in champs.items() if v}
    champs = appliquer_deductions(fiche.champs, champs, le.date())
    nom = champs.get("nom", fiche.nom)
    prenom = champs.get("prenom", fiche.prenom)
    return replace(fiche, champs=champs, nom=nom, prenom=prenom, maj_par=par, maj_le=le)


def annuler(fiche: FicheImport, par: str, le: datetime) -> FicheImport:
    """L'import n'est plus voulu : la fiche sort de la liste (rien ne
    s'efface en base)."""
    return replace(fiche, annulee_le=le, annulee_par=par, maj_par=par, maj_le=le)


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
    valeurs["associes"] = associes_du_registre(
        [(p.nom, p.prenoms) for p in officielle.personnes], officielle.forme_juridique
    )
    return {k: v for k, v in valeurs.items() if v}


def preremplir(
    fiche: FicheImport, officielle: FicheOfficielle, par: str, le: datetime
) -> FicheImport:
    """Les registres remplissent les champs vides, et remplacent ce qui venait
    de la lecture précédente (un SIREN corrigé) ; une saisie n'est jamais
    écrasée. La lecture est gardée avec la fiche."""
    anciens = depuis_registre(fiche.registre) if fiche.registre else {}
    champs = dict(fiche.champs)
    for cle, valeur in depuis_registre(officielle).items():
        if not champs.get(cle) or champs[cle] == anciens.get(cle):
            champs[cle] = valeur
    champs = appliquer_deductions(fiche.champs, champs, le.date())
    return replace(
        fiche,
        champs=champs,
        registre=officielle,
        nom=champs.get("nom", fiche.nom),
        prenom=champs.get("prenom", fiche.prenom),
        maj_par=par,
        maj_le=le,
    )


def lire_emplacement(emplacement: str) -> tuple[str, str, int | None]:
    """« reprise:liasse:2025 » → (section, catégorie, exercice)."""
    morceaux = emplacement.split(":")
    if len(morceaux) not in (2, 3) or morceaux[0] not in {s.cle for s in SECTIONS}:
        raise SaisieInvalide(f"Emplacement inconnu : {emplacement}.")
    annee = morceaux[2] if len(morceaux) == 3 else ""
    if annee and not annee.isdigit():
        raise SaisieInvalide(f"Emplacement inconnu : {emplacement}.")
    return morceaux[0], morceaux[1], int(annee) if annee else None


def document_import(
    id_: str,
    fiche: FicheImport,
    emplacement: str,
    nom_fichier: str,
    type_mime: str,
    contenu: bytes,
    par: str,
    le: datetime,
) -> DocumentImport:
    """Un document déposé à un emplacement de la fiche, avec l'empreinte de
    son contenu."""
    _section, categorie, exercice = lire_emplacement(emplacement)
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
        emplacement=emplacement,
    )


def champs_du_registre(fiche: FicheImport) -> list[str]:
    """Les champs qui ont encore la valeur lue aux registres (AXE-946)."""
    if fiche.registre is None:
        return []
    lus = depuis_registre(fiche.registre)
    return sorted(cle for cle, valeur in lus.items() if fiche.champs.get(cle) == valeur)
