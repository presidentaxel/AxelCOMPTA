"""Compare deux modèles de catégorisation sur le jeu gelé et dit si le
candidat peut être promu (AXE-904).

Le candidat (`entrainer_modele.py --decisions --modele modeles/<version>.joblib`)
est appris sur les décisions réelles en plus de l'audit, jamais sur le jeu
gelé (AXE-902). Chaque modèle est mesuré comme en production : sa propre
calibration, ses seuils, ses classes imputables.

Le candidat n'est promouvable que s'il fait au moins aussi bien que le
champion sur les trois mesures suivantes :

* l'exactitude sur le jeu gelé ;
* la justesse des imputations automatiques, qui doit aussi rester d'au moins 95 % ;
* la part des lignes proposées.

Attention : un champion entraîné avant AXE-902 a vu les dossiers du jeu
gelé ; ses chiffres sont alors optimistes, et la comparaison penche en sa
faveur.

Usage, depuis _AUDIT_DONNEES/ :

    python comparer_modeles.py --champion modeles/tfidf_logreg_v2.joblib \\
        --candidat modeles/tfidf_logreg_v3.joblib --entree resultats/fec_ml_taxonomie_v2.csv

Code de sortie 0 : promouvable (publier avec backend/scripts/publier_modele.py,
puis poser AXELCOMPTA_MODELE_VERSION) ; 1 : garder le champion.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from entrainer_modele import ENTREE, lignes_audit

JUSTESSE_IMPUTATION_MIN = 0.95


@dataclass
class Mesure:
    exactitude: float
    proposees: float
    justesse_proposees: float
    imputees: float
    justesse_imputees: float

    def lignes(self, nom: str) -> str:
        return (
            f"{nom:10s} exactitude {self.exactitude * 100:5.1f} % | proposées "
            f"{self.proposees * 100:5.1f} % (justes {self.justesse_proposees * 100:5.1f} %) | "
            f"imputées {self.imputees * 100:5.1f} % (justes {self.justesse_imputees * 100:5.1f} %)"
        )


def _part(masque: np.ndarray, justes: np.ndarray) -> tuple[float, float]:
    return float(masque.mean()), float(justes[masque].mean()) if masque.any() else 1.0


def mesurer(chemin: Path, x: np.ndarray, y: np.ndarray) -> Mesure:
    modele = joblib.load(chemin)
    reglages = json.loads(chemin.with_suffix(".calibration.json").read_text(encoding="utf-8"))
    probabilites = modele.predict_proba(x)
    predites = modele.classes_[probabilites.argmax(1)]
    courbe = reglages["calibration"]
    # Comme la régression isotone (clip), par interpolation entre ses seuils.
    calibrees = np.interp(probabilites.max(1), courbe["x"], courbe["y"])
    justes = predites == y
    proposees = calibrees >= reglages["seuil_proposition"]
    imputees = (calibrees >= reglages["seuil_imputation"]) & np.isin(
        predites, reglages["classes_imputables"]
    )
    return Mesure(float(justes.mean()), *_part(proposees, justes), *_part(imputees, justes))


def promouvable(champion: Mesure, candidat: Mesure) -> bool:
    return (
        candidat.exactitude >= champion.exactitude
        and candidat.justesse_imputees >= JUSTESSE_IMPUTATION_MIN
        and candidat.proposees >= champion.proposees
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--champion", type=Path, required=True)
    parser.add_argument("--candidat", type=Path, required=True)
    parser.add_argument("--entree", type=Path, default=ENTREE)
    args = parser.parse_args()

    lignes = lignes_audit(args.entree, gelees=True)
    x = np.array([t for _, t, _ in lignes])
    y = np.array([c for _, _, c in lignes])
    champion, candidat = mesurer(args.champion, x, y), mesurer(args.candidat, x, y)
    print(f"Jeu gelé : {len(lignes)} lignes, {len({g for g, _, _ in lignes})} dossiers")
    print(champion.lignes("champion"))
    print(candidat.lignes("candidat"))
    if promouvable(champion, candidat):
        print("Promouvable : le candidat fait au moins aussi bien partout.")
        return 0
    print("Garder le champion.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
