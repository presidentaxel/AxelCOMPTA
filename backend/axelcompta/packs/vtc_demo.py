"""Pack VTC réduit pour la démo (doc 17 §3, §4bis).

Charge les fichiers de l'audit directement — `regles_regex.csv` (12 règles)
et `mapping_pcg_categorie.csv` — plutôt que de les dupliquer ici
(packs/README.md). Ces deux fichiers sont commités (contrairement au CSV
FEC et au modèle ML, gitignorés) : toujours présents sur un clone du repo.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from axelcompta.core.pcg import nature_depuis_compte as nature_depuis_compte

# backend/axelcompta/packs/vtc_demo.py -> racine du repo
RACINE_PACKS_VTC = Path(__file__).resolve().parents[3] / "_AUDIT_DONNEES" / "packs_vtc"
CHEMIN_REGLES_PAR_DEFAUT = RACINE_PACKS_VTC / "regles_regex.csv"
CHEMIN_MAPPING_PAR_DEFAUT = RACINE_PACKS_VTC / "mapping_pcg_categorie.csv"
CHEMIN_CATEGORIES_BANQUE_PAR_DEFAUT = RACINE_PACKS_VTC / "categories_bridge.csv"


@dataclass(frozen=True, slots=True)
class RegleCategorisation:
    """Une règle du pack : motif regex, catégorie, confiance (doc 05 §2)."""

    motif: re.Pattern[str]
    categorie: str
    confiance: str
    # Plancher en centimes (AXE-837), réglable dans le pack : sous ce montant,
    # la règle propose sa catégorie sans l'imputer seule (un café chez Total
    # n'est pas un plein ; un vrai plein peut, par hasard, passer en dessous).
    montant_min_cts: int | None = None

    def sous_le_plancher(self, montant_cts: int) -> bool:
        return self.montant_min_cts is not None and abs(montant_cts) < self.montant_min_cts


def charger_regles(chemin: Path | None = None) -> tuple[RegleCategorisation, ...]:
    """`re.IGNORECASE` forcé sur toutes les règles, pas seulement celles qui
    ont `(?i)` inline dans le CSV — bug trouvé en testant sur un vrai
    dossier complet (doc 17 §2, 2026-09-05) : seule 1 des 12 règles du pack
    (`carburant`) a `(?i)`, les 11 autres — dont `recettes_plateformes`, le
    revenu principal d'un chauffeur — ne matchaient donc jamais un libellé
    bancaire en MAJUSCULES (le format usuel des relevés bancaires réels).
    Sur un vrai dossier testé, ça faisait tomber le CA à quelques centaines
    d'euros au lieu de plusieurs dizaines de milliers.
    """
    chemin = chemin or CHEMIN_REGLES_PAR_DEFAUT
    with chemin.open(newline="", encoding="utf-8") as fichier:
        return tuple(
            RegleCategorisation(
                re.compile(ligne["regex"], re.IGNORECASE),
                ligne["categorie"],
                ligne["confiance"],
                _plancher(ligne.get("montant_min_cts")),
            )
            for ligne in csv.DictReader(fichier)
        )


def _plancher(valeur: str | None) -> int | None:
    texte = (valeur or "").strip()
    return int(texte) if texte else None


def plancher_de(categorie: str, regles: tuple[RegleCategorisation, ...]) -> int | None:
    """Le plancher d'une catégorie dans le pack (le plus haut de ses règles),
    lu aussi par les détecteurs d'anomalies (AXE-836)."""
    planchers = [
        r.montant_min_cts for r in regles if r.categorie == categorie and r.montant_min_cts
    ]
    return max(planchers) if planchers else None


# Corrections explicites au "premier compte listé" — trouvées en testant sur
# un vrai dossier complet (doc 17 §2, reformulé 2026-09-05) : le premier
# compte du mapping n'est pas classe 6/7 alors qu'une alternative correcte
# existe, ce qui exclut silencieusement la catégorie du compte de résultat.
# `recettes_plateformes` est le cas le plus grave : c'est le revenu principal
# d'un chauffeur, exclu du CA s'il tombe sur 418 (créance temporaire) au lieu
# de 706 (produit réel). `immobilisation_vehicule` n'est PAS corrigée ici :
# son premier choix (218, hors compte de résultat) est correct pour l'achat
# d'un véhicule (le cas courant) — la seule alternative 6/7 (775, produit de
# cession) ne s'applique qu'à la revente ; la forcer casserait le cas normal.
CORRECTIONS_COMPTE_PAR_CATEGORIE = {
    "recettes_plateformes": "706",  # produit réel, pas 418 (créance temporaire)
    "honoraires_comptable_juridique": "6226",  # charge réelle, pas 201 (immobilisation)
    "charges_sociales_impots": "645",  # charge réelle, pas 431 (compte de tiers URSSAF)
    # 6712 (pénalités, amendes fiscales et pénales) plutôt que 671, trop
    # large : c'est ce compte précis que la clôture réintègre au résultat
    # fiscal (CGI art. 39-2, 2033-B ligne 330).
    "amendes_infractions": "6712",
}


def charger_compte_par_categorie(chemin: Path | None = None) -> dict[str, str]:
    """Premier compte listé par catégorie dans le mapping — choix déterministe,
    **pas un jugement comptable validé** (le mapping est un brouillon
    d'audit, doc 12 §0.2 : « à densifier avec le comptable avant
    production »). Plusieurs comptes PCG peuvent correspondre à une même
    catégorie ; on ne tranche pas ici lequel est le bon en général, sauf les
    quelques corrections explicites ci-dessus quand le premier choix casse
    silencieusement le compte de résultat.
    """
    chemin = chemin or CHEMIN_MAPPING_PAR_DEFAUT
    comptes: dict[str, str] = {}
    with chemin.open(newline="", encoding="utf-8") as fichier:
        for ligne in csv.DictReader(fichier):
            comptes.setdefault(ligne["categorie"], ligne["prefixe_compte_pcg_normalise"])
    comptes.update(CORRECTIONS_COMPTE_PAR_CATEGORIE)
    return comptes


def charger_categories_banque(chemin: Path | None = None) -> dict[str, str]:
    """`{category_id Bridge: catégorie du pack}` (AXE-826). Une catégorie de
    la banque absente de la table ne propose rien. Indice seulement : le
    pipeline n'impute jamais sur cette seule base."""
    chemin = chemin or CHEMIN_CATEGORIES_BANQUE_PAR_DEFAUT
    with chemin.open(newline="", encoding="utf-8") as fichier:
        return {
            ligne["category_id"].strip(): ligne["categorie"].strip()
            for ligne in csv.DictReader(fichier)
            if ligne["category_id"].strip() and ligne["categorie"].strip()
        }
