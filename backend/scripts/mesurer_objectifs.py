"""Mesure les objectifs V1 de la catégorisation sur un jeu étiqueté (AXE-816).

Le jeu est un CSV, une opération par ligne :
    libelle,montant_cts,categorie[,type_operation,categorie_banque,date,compte_bancaire]
`categorie` est la catégorie juste. Sans `compte_bancaire`, les virements
entre deux comptes du dossier (enveloppes « cotisation TVA », « carburant »)
ne sont pas appariés comme dans la synchro et passent pour des erreurs : le
script le signale. Le jeu gelé (AXE-423) ne sert jamais à
entraîner ni à choisir un seuil.

Le pipeline est celui de la synchro : règles du pack, puis modèle (si
`--modele`), puis la même politique d'imputation (`synchro.choisir_compte`).
Sortie : tableau Markdown daté, par objectif, par étage et par catégorie.
Aucun libellé n'est affiché.

Usage, depuis backend/ :
    python scripts/mesurer_objectifs.py jeu.csv
    python scripts/mesurer_objectifs.py jeu.csv \
        --modele ../_AUDIT_DONNEES/modeles/tfidf_logreg_v2.joblib
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from axelcompta.categorize.ml_fallback import charger_calibration, charger_modele
from axelcompta.categorize.models import Etage
from axelcompta.categorize.objectifs import (
    ETAGE_AUCUN,
    ETAGE_MODELE,
    ETAGE_REGLE,
    Observation,
    mesurer,
    par_categorie,
    par_etage,
    tableau,
)
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT, RulesAndMlPipeline
from axelcompta.core.ids import DossierId, TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.packs.vtc_demo import (
    charger_categories_banque,
    charger_compte_par_categorie,
    charger_regles,
)
from axelcompta.workflow.synchro import COMPTE_ATTENTE, choisir_compte

_JOUR_PAR_DEFAUT = date(2026, 1, 1)
AVERTISSEMENT_SANS_COMPTE = (
    "> Jeu sans colonne `compte_bancaire` : les virements internes ne sont pas "
    "appariés, la précision est sous-estimée."
)
_ETAGES = {Etage.REGLE: ETAGE_REGLE, Etage.ML: ETAGE_MODELE, Etage.BANQUE: "banque"}


def _lire(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(newline="", encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def _transactions(lignes: list[dict[str, str]]) -> list[NormalizedTransaction]:
    return [
        NormalizedTransaction(
            id=TransactionId(f"t{rang}"),
            dossier_id=DossierId("mesure"),
            date=date.fromisoformat(ligne["date"]) if ligne.get("date") else _JOUR_PAR_DEFAUT,
            montant_cts=int(ligne["montant_cts"]),
            libelle=ligne["libelle"],
            source_provider="mesure",
            raw_payload={},
            type_operation=ligne.get("type_operation") or None,
            categorie_banque=ligne.get("categorie_banque") or None,
            compte_bancaire=ligne.get("compte_bancaire") or None,
        )
        for rang, ligne in enumerate(lignes)
    ]


def observer(lignes: list[dict[str, str]], pipeline: RulesAndMlPipeline) -> list[Observation]:
    comptes = charger_compte_par_categorie()
    propositions = pipeline.categoriser_lot(DossierId("mesure"), _transactions(lignes))
    observations = []
    for ligne, proposition in zip(lignes, propositions, strict=True):
        sans_avis = proposition.categorie == CATEGORIE_PAR_DEFAUT
        observations.append(
            Observation(
                etage=ETAGE_AUCUN if sans_avis else _ETAGES.get(proposition.etage, ETAGE_AUCUN),
                impute=choisir_compte(proposition, comptes) != COMPTE_ATTENTE,
                proposee=None if sans_avis else proposition.categorie,
                vraie=ligne["categorie"],
            )
        )
    return observations


def _detail(titre: str, colonnes: str, lignes: dict[str, tuple[int, int, int]]) -> str:
    corps = [f"| {cle} | {a} | {b} | {c} |" for cle, (a, b, c) in lignes.items()]
    return "\n".join([f"### {titre}", "", colonnes, "| -- | -- | -- | -- |", *corps])


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("jeu", type=Path)
    parseur.add_argument("--modele", type=Path, default=None)
    arguments = parseur.parse_args()
    modele = charger_modele(arguments.modele) if arguments.modele else None
    calibration = charger_calibration(arguments.modele) if arguments.modele else None
    pipeline = RulesAndMlPipeline(
        regles=charger_regles(),
        modele=modele,
        calibration=calibration,
        categories_banque=charger_categories_banque(),
    )
    lignes = _lire(arguments.jeu)
    observations = observer(lignes, pipeline)
    entete = f"{len(observations)} opérations, jeu {arguments.jeu.name}"
    print(f"Mesure du {date.today():%d/%m/%Y} — {entete}", end="\n\n")
    if not any(ligne.get("compte_bancaire") for ligne in lignes):
        print(AVERTISSEMENT_SANS_COMPTE, end="\n\n")
    print(tableau(mesurer(observations), "Objectifs V1 (doc 01 §6)"), "\n")
    print(
        _detail(
            "Par étage",
            "| Étage | Opérations | Justes | Imputées fausses |",
            par_etage(observations),
        ),
        "\n",
    )
    print(
        _detail(
            "Par catégorie",
            "| Catégorie | Opérations | Imputées seules | Imputées justes |",
            par_categorie(observations),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
