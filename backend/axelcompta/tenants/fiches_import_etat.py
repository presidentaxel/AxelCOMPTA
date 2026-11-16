"""Ce qui manque à une fiche d'import, et les exercices à reprendre (AXE-941). Pur.

Les exercices se déduisent de la date de création, de la date de clôture
(« 31/12 ») et, si on la connaît, de la date de première clôture. Pour un
exercice clos, on attend la liasse et le FEC (ou, sans FEC, la balance et le
grand livre). Seul le **dernier exercice clos** est indispensable : c'est lui
qui donne le report à nouveau. Les plus anciens, depuis 2024, se reprennent
s'ils sont disponibles.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from .fiches_import import (
    CATEGORIES_DOCUMENTS,
    DOCUMENTS_ADMINISTRATIFS,
    SECTIONS,
    DocumentImport,
    FicheImport,
    Section,
)
from .import_dossiers import identifiant

ANNEE_MIN_REPRISE = 2024
EXERCICES_MAX = 40  # garde-fou : une date de création absurde ne boucle pas


@dataclass(frozen=True, slots=True)
class Piece:
    categorie: str
    libelle: str
    attendue: bool  # indispensable ; sinon « si vous l'avez »
    recue: bool


@dataclass(frozen=True, slots=True)
class Exercice:
    debut: date
    fin: date
    etat: Literal["clos", "en_cours"]
    pieces: tuple[Piece, ...]

    @property
    def annee(self) -> int:
        return self.fin.year


@dataclass(frozen=True, slots=True)
class EtatSection:
    cle: str
    libelle: str
    complet: bool
    manquants: tuple[str, ...]


def _cloture_dans(annee: int, jour: int, mois: int) -> date:
    return date(annee, mois, min(jour, calendar.monthrange(annee, mois)[1]))


def _bornes(champs: Mapping[str, str], aujourd_hui: date) -> list[tuple[date, date]]:
    """(début, fin) de chaque exercice, de la création à l'exercice en cours."""
    try:
        creation = date.fromisoformat(champs["date_creation"])
        jour, mois = (int(x) for x in champs["cloture"].split("/"))
    except (KeyError, ValueError):
        return []
    premiere = champs.get("premiere_cloture")
    fin = date.fromisoformat(premiere) if premiere else _cloture_dans(creation.year, jour, mois)
    if fin <= creation:
        fin = _cloture_dans(fin.year + 1, jour, mois)
    bornes = [(creation, fin)]
    while fin < aujourd_hui and len(bornes) < EXERCICES_MAX:
        debut, fin = fin + timedelta(days=1), _cloture_dans(fin.year + 1, jour, mois)
        bornes.append((debut, fin))
    return bornes


def _pieces(
    annee: int, documents: Sequence[DocumentImport], indispensable: bool
) -> tuple[Piece, ...]:
    recues = {d.categorie for d in documents if d.exercice == annee}
    avec_fec = "fec" in recues
    return (
        Piece("liasse", CATEGORIES_DOCUMENTS["liasse"], indispensable, "liasse" in recues),
        Piece("fec", CATEGORIES_DOCUMENTS["fec"], indispensable, avec_fec),
        Piece(
            "balance",
            CATEGORIES_DOCUMENTS["balance"],
            indispensable and not avec_fec,
            "balance" in recues,
        ),
        Piece(
            "grand_livre",
            CATEGORIES_DOCUMENTS["grand_livre"],
            indispensable and not avec_fec,
            "grand_livre" in recues,
        ),
    )


def exercices(
    champs: Mapping[str, str], documents: Sequence[DocumentImport], aujourd_hui: date
) -> list[Exercice]:
    """Les exercices clos depuis 2024 et l'exercice en cours, du plus ancien
    au plus récent. Vide sans date de création ni date de clôture."""
    bornes = [(d, f) for d, f in _bornes(champs, aujourd_hui) if f.year >= ANNEE_MIN_REPRISE]
    clos = [f for _d, f in bornes if f < aujourd_hui]
    dernier_clos = max(clos) if clos else None
    resultat = []
    for debut, fin in bornes:
        if fin >= aujourd_hui:
            resultat.append(Exercice(debut, fin, "en_cours", ()))
            continue
        pieces = _pieces(fin.year, documents, indispensable=fin == dernier_clos)
        resultat.append(Exercice(debut, fin, "clos", pieces))
    return resultat


def _manquants_champs(section: Section, champs: Mapping[str, str]) -> list[str]:
    manquants = [c.libelle for c in section.champs if c.obligatoire and not champs.get(c.cle)]
    if section.cle == "fiscalite" and champs.get("regime_imposition") == "option_IR":
        if not champs.get("option_ir_debut"):
            manquants.append("Première année de l'option IR")
    return manquants


def _manquants_reprise(champs: Mapping[str, str], liste: Sequence[Exercice]) -> list[str]:
    if not champs.get("date_creation") or not champs.get("cloture"):
        return ["Date de création et date de clôture (catégorie Entreprise)"]
    return [f"{p.libelle} {e.annee}" for e in liste for p in e.pieces if p.attendue and not p.recue]


def etat_sections(
    fiche: FicheImport, documents: Sequence[DocumentImport], aujourd_hui: date
) -> list[EtatSection]:
    """Chaque catégorie : complète, ou ce qui lui manque."""
    liste = exercices(fiche.champs, documents, aujourd_hui)
    deposes = {d.categorie for d in documents}
    etats = []
    for section in SECTIONS:
        manquants = _manquants_champs(section, fiche.champs)
        if section.cle == "reprise":
            manquants += _manquants_reprise(fiche.champs, liste)
        if section.cle == "documents":
            manquants += [
                CATEGORIES_DOCUMENTS[c] for c in DOCUMENTS_ADMINISTRATIFS if c not in deposes
            ]
        etats.append(EtatSection(section.cle, section.libelle, not manquants, tuple(manquants)))
    return etats


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
