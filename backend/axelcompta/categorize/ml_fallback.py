"""Fallback ML — étage 2 (doc 05 §3). Charge le modèle déjà entraîné
(`_AUDIT_DONNEES/modeles/<version>.joblib`, gitignoré ; version réglée par
`AXELCOMPTA_MODELE_VERSION`, `tfidf_logreg_v2` par défaut ; produit par
`_AUDIT_DONNEES/entrainer_modele.py`). S'il manque sur le poste, il est
récupéré du bucket privé au démarrage (`axelcompta.modeles_distants`,
AXE-847). Ne l'importe jamais comme code — chargé
comme artefact (doc 03 §3, « personne n'importe ml au runtime »).

Reproduit exactement le featurizing de
`_AUDIT_DONNEES/entrainer_modele.py` (`texte`, `bucket_montant`, identiques
à ceux du v1) : le modèle a été entraîné sur ce format précis, un
featurizing différent donnerait des prédictions incohérentes.

**Signe.** Le modèle a appris sur des montants FEC (charge positive, recette
négative). Une `NormalizedTransaction` suit la convention bancaire (argent
reçu positif, doc 13 §4.1) : le montant est retourné avant le featurizing.
Jusqu'au 2026-09-27 il ne l'était pas, et chaque encaissement était présenté
au modèle comme une dépense.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from axelcompta.core.errors import DomaineError

# backend/axelcompta/categorize/ml_fallback.py -> racine du repo
DOSSIER_MODELES = Path(__file__).resolve().parents[3] / "_AUDIT_DONNEES" / "modeles"

# AXE-847 : la version attendue est un réglage, pas un nom de fichier codé en
# dur. Le fichier `<version>.joblib` est récupéré du stockage s'il manque
# (`axelcompta.modeles_distants`).
VARIABLE_VERSION = "AXELCOMPTA_MODELE_VERSION"
VERSION_PAR_DEFAUT = "tfidf_logreg_v2"


def version_attendue(environ: Mapping[str, str] | None = None) -> str:
    valeurs = os.environ if environ is None else environ
    return valeurs.get(VARIABLE_VERSION, "").strip() or VERSION_PAR_DEFAUT


def chemin_modele(version: str, dossier: Path = DOSSIER_MODELES) -> Path:
    return dossier / f"{version}.joblib"


CHEMIN_MODELE_PAR_DEFAUT = chemin_modele(version_attendue())


class ModeleMlIndisponible(DomaineError):
    """Le modèle .joblib n'est pas présent sur ce poste (gitignoré) — erreur
    attendue, pas un bug (doc 08 §5)."""


class ModeleMlCorrompu(ModeleMlIndisponible):
    """Le fichier ne correspond pas à son empreinte `.sha256` (AXE-825)."""


# AXE-825 : sans modèle, la synchro s'arrête. Ce repli n'est permis qu'en
# développement et en test, et seulement s'il est demandé.
VARIABLE_SANS_MODELE = "AXELCOMPTA_SANS_MODELE"


def repli_sans_modele_permis(environ: Mapping[str, str] | None = None) -> bool:
    valeurs = os.environ if environ is None else environ
    return valeurs.get(VARIABLE_SANS_MODELE, "").strip() == "1"


def chemin_empreinte(chemin: Path) -> Path:
    """`tfidf_logreg_v2.joblib.sha256`, écrit à l'entraînement."""
    return chemin.with_name(chemin.name + ".sha256")


def verifier_empreinte(chemin: Path) -> None:
    """Compare le fichier à son empreinte, si elle existe. Une empreinte
    absente n'est pas une erreur : les modèles d'avant AXE-825 n'en ont pas."""
    empreinte = chemin_empreinte(chemin)
    if not empreinte.is_file():
        return
    attendue = empreinte.read_text(encoding="utf-8").split()[0].strip().lower()
    reelle = hashlib.sha256(chemin.read_bytes()).hexdigest()
    if reelle != attendue:
        raise ModeleMlCorrompu(f"{chemin} : empreinte {reelle[:12]}…, attendue {attendue[:12]}…")


class ModeleSklearn(Protocol):
    """Juste assez du contrat sklearn Pipeline pour ne pas dépendre du type
    concret dans le reste du code (doc 08 §2.6 : pas d'alias mutable partagé,
    ici on type le strict nécessaire)."""

    classes_: Any

    def predict(self, x: list[str]) -> Any: ...
    def predict_proba(self, x: list[str]) -> Any: ...


# Sens possibles d'une catégorie, lus sur le jeu d'entraînement (plus de 95 %
# des lignes dans un seul sens) et conformes au plan comptable : un produit
# n'est jamais un décaissement, une charge jamais un encaissement. Les autres
# catégories (frais bancaires remboursés, cession de véhicule, remboursement
# d'assurance ou de cotisations…) acceptent les deux sens.
ENCAISSEMENTS_SEULEMENT = frozenset({"recettes_plateformes", "subventions"})
DECAISSEMENTS_SEULEMENT = frozenset(
    {
        "a_verifier_location_materiel",
        "abonnements_logiciels",
        "amendes_infractions",
        "assurance_vehicule",
        "carburant",
        "entretien_reparation_vehicule",
        "fournitures_administratives",
        "honoraires_comptable_juridique",
        "interets_emprunts",
        "peage_stationnement",
        "remuneration_dirigeant",
        "repas_et_receptions",
        "sous_traitance_chauffeurs",
        "telecommunications",
        "visite_medicale_vtc",
    }
)


def _bucket_montant(montant_cts: int) -> str:
    """Log-bucket signé, identique à `entrainer_modele_baseline.py`."""
    montant = montant_cts / 100
    if montant == 0:
        return "[M0]"
    signe = "+" if montant > 0 else "-"
    bucket = int(math.log10(abs(montant))) if abs(montant) >= 1 else 0
    return f"[M{signe}{bucket}]"


def texte_pour_modele(libelle: str, montant_cts: int) -> str:
    """`montant_cts` en convention FEC (charge positive), celle de l'entraînement."""
    return f"{libelle} {_bucket_montant(montant_cts)}"


def sens_compatible(categorie: str, montant_bancaire_cts: int) -> bool:
    if montant_bancaire_cts > 0:
        return categorie not in DECAISSEMENTS_SEULEMENT
    if montant_bancaire_cts < 0:
        return categorie not in ENCAISSEMENTS_SEULEMENT
    return True


def charger_modele(chemin: Path | None = None) -> ModeleSklearn:
    chemin = chemin or CHEMIN_MODELE_PAR_DEFAUT
    if not chemin.is_file():
        raise ModeleMlIndisponible(str(chemin))
    verifier_empreinte(chemin)
    import joblib  # import différé : coûteux, inutile si le modèle est absent

    modele: ModeleSklearn = joblib.load(chemin)
    return modele


@dataclass(frozen=True, slots=True)
class Calibration:
    """Écrite par `_AUDIT_DONNEES/entrainer_modele.py` à côté du modèle
    (`<modèle>.calibration.json`) : la courbe qui transforme la probabilité
    brute en chance réelle d'avoir raison (régression isotone sur les
    prédictions hors échantillon), le seuil de proposition et la politique
    d'imputation automatique, catégorie par catégorie (doc 07 §3.4, §4)."""

    x: tuple[float, ...]
    y: tuple[float, ...]
    seuil_proposition: float
    seuil_imputation: float
    classes_imputables: frozenset[str]

    def confiance(self, brute: float) -> float:
        """Interpolation linéaire entre les paliers de la courbe, bornée."""
        if not self.x:
            return brute
        if brute <= self.x[0]:
            return self.y[0]
        if brute >= self.x[-1]:
            return self.y[-1]
        i = bisect_right(self.x, brute)
        x0, x1, y0, y1 = self.x[i - 1], self.x[i], self.y[i - 1], self.y[i]
        return y0 if x1 == x0 else y0 + (y1 - y0) * (brute - x0) / (x1 - x0)

    def seuil_imputation_de(self, categorie: str) -> float:
        """`inf` : cette catégorie ne s'impute jamais sans regard humain."""
        return self.seuil_imputation if categorie in self.classes_imputables else math.inf


def charger_calibration(chemin_modele: Path | None = None) -> Calibration | None:
    """`None` si le fichier manque : les seuils bruts historiques s'appliquent."""
    chemin = (chemin_modele or CHEMIN_MODELE_PAR_DEFAUT).with_suffix(".calibration.json")
    if not chemin.is_file():
        return None
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    return Calibration(
        x=tuple(float(v) for v in donnees["calibration"]["x"]),
        y=tuple(float(v) for v in donnees["calibration"]["y"]),
        seuil_proposition=float(donnees["seuil_proposition"]),
        seuil_imputation=float(donnees["seuil_imputation"]),
        classes_imputables=frozenset(donnees["classes_imputables"]),
    )


def predire(modele: ModeleSklearn, libelle: str, montant_cts: int) -> tuple[str, float]:
    """Une seule transaction ; voir `predire_lot`."""
    return predire_lot(modele, [(libelle, montant_cts)])[0]


def predire_lot(
    modele: ModeleSklearn,
    transactions: Sequence[tuple[str, int]],
    calibration: Calibration | None = None,
) -> list[tuple[str, float]]:
    """(catégorie, confiance) par `(libelle, montant_cts)`, montants en
    convention bancaire (argent reçu positif), en un seul appel au modèle.

    Les catégories de sens contraire au flux sont écartées. La confiance
    reste la probabilité brute de la catégorie retenue, sans renormaliser :
    si le modèle misait surtout sur une catégorie impossible, la confiance
    baisse et l'étage suivant s'abstient."""
    if not transactions:
        return []
    textes = [texte_pour_modele(libelle, -montant) for libelle, montant in transactions]
    classes = [str(c) for c in modele.classes_]
    resultat: list[tuple[str, float]] = []
    for probabilites, (_, montant) in zip(modele.predict_proba(textes), transactions, strict=True):
        candidates = [
            (float(probabilite), categorie)
            for probabilite, categorie in zip(probabilites, classes, strict=True)
            if sens_compatible(categorie, montant)
        ]
        if not candidates:
            resultat.append(("non_categorise_a_verifier", 0.0))
            continue
        confiance, categorie = max(candidates)
        if calibration is not None:
            confiance = calibration.confiance(confiance)
        resultat.append((categorie, confiance))
    return resultat
