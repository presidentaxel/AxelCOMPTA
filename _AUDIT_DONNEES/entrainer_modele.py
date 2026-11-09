"""Entraîne le modèle de catégorisation v2 (successeur de
`entrainer_modele_baseline.py`, gardé tel quel pour reproduire le v1).

Ce qui change par rapport au v1 (2026-09-27) :

- **Étiquettes étendues** : `fec_ml_taxonomie_v2.csv` (construire_taxonomie.py)
  garde les transactions dont la seule contrepartie est un compte courant
  d'associé (455), la paie nette (421) ou un virement interne (580), jetées
  jusque-là faute de jambe 6/7.
- **Pondération des classes en racine** de `balanced`. `balanced` gonflait
  les classes rares au point qu'un gros virement Uber sortait en
  subventions ; sans pondération, les classes rares disparaissent (rappel
  des abonnements logiciels à 2 %). La racine est le compromis mesuré : à
  précision égale, plus de lignes reçoivent une proposition.
- **Évaluation par validation croisée en 5 plis, groupée par dossier** (le v1
  n'avait qu'un seul découpage de 14 dossiers de test). Un dossier n'est
  jamais à la fois en entraînement et en test. Le modèle écrit ensuite est
  entraîné sur tout.
- **Calibration et politique d'imputation** (2026-09-27) : une régression
  isotone sur les prédictions hors échantillon de la validation croisée
  transforme la probabilité brute en chance réelle d'avoir raison. À côté du
  modèle, `<modèle>.calibration.json` porte cette courbe, le seuil de
  proposition (0,6 calibré) et la politique d'imputation automatique : 0,95
  calibré, seulement pour les catégories qui atteignent 95 % de justesse sur
  au moins 30 lignes à ce seuil, jamais les catégories à enjeu ni « à
  vérifier ». Les chiffres du rapport sont mesurés en validation croisée
  imbriquée : calibration et politique choisies sur 4 plis, mesurées sur le
  5e.
- **Décisions des utilisateurs** (`--decisions`) : chaque catégorie tranchée
  à la main dans l'application devient un exemple d'entraînement, lu en base
  au moment de l'entraînement et jamais écrit dans un fichier. Les dossiers
  de démo (`DEMO_`, fabriqués) sont exclus. Leur dossier reste un groupe de la
  validation croisée : le score ne compte jamais une ligne d'un dossier
  dont d'autres lignes ont servi à l'entraînement du même pli.

Ce que l'évaluation mesure toujours : la généralisation du mapping PCG à des
dossiers jamais vus, pas l'exactitude « vraie » (la relecture des 500 lignes
reste la seule vérité terrain, voir generer_echantillon_relecture.py).

Usage, depuis _AUDIT_DONNEES/ :

    python entrainer_modele.py                  # jeu d'audit seul
    python entrainer_modele.py --decisions      # + décisions en base (.env racine)
"""

import argparse
import hashlib
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

ENTREE = Path("resultats/fec_ml_taxonomie_v2.csv")
SORTIE_MODELE = Path("modeles/tfidf_logreg_v2.joblib")
SORTIE_RAPPORT = Path("resultats/rapport_modele_v2.txt")

EXCLUES = {
    "dotations_amortissements",
    "operation_capital_hors_perimetre",
    "non_categorise_a_verifier",
}
MIN_EXEMPLES_PAR_CLASSE = 15
PLIS = 5
SEUILS = (0.5, 0.6, 0.7, 0.9)
# Échelle calibrée (chance d'avoir raison), voir l'en-tête.
SEUIL_PROPOSITION = 0.6
SEUIL_IMPUTATION = 0.95
PRECISION_IMPUTATION = 0.95
SUPPORT_IMPUTATION = 30
# Jamais imputées sans regard humain, quelle que soit leur précision
# (doc 07 §3.4 : classes à enjeu) : leur compte dépend du statut ou de la
# situation, ou l'erreur change le résultat imposable.
JAMAIS_IMPUTEES = {
    "immobilisation_vehicule",
    "remuneration_dirigeant",
    "compte_courant_associe",
    "salaires_personnel",
    "subventions",
    # Mélange d'achats professionnels et personnels relevé par l'audit
    # (rapport_audit_dataset.md, règle « usage personnel suspect ») : un achat
    # Amazon ou un repas passé seul en charge déductible est le risque que le
    # chauffeur doit pouvoir voir.
    "fournitures_administratives",
    "repas_et_receptions",
}

# Catégories de l'application qui n'existent pas sous ce nom dans la
# taxonomie d'entraînement. Une dépense personnelle tranchée par le
# chauffeur est passée en compte courant d'associé (455) dans l'historique
# FEC : même classe.
CATEGORIE_DECISION_VERS_TAXONOMIE = {"usage_personnel": "compte_courant_associe"}
_SUFFIXE_CATEGORIE = re.compile(r"\s+\([a-z0-9_]+\)$")


def bucket_montant(montant: float) -> str:
    """Identique à `entrainer_modele_baseline.bucket_montant` et à
    `backend/axelcompta/categorize/ml_fallback._bucket_montant`."""
    if montant == 0:
        return "[M0]"
    signe = "+" if montant > 0 else "-"
    bucket = int(math.log10(abs(montant))) if abs(montant) >= 1 else 0
    return f"[M{signe}{bucket}]"


def texte(libelle: str, montant_fec: float) -> str:
    return f"{libelle} {bucket_montant(montant_fec)}"


def poids_racine(etiquettes: list[str]) -> dict[str, float]:
    compte = Counter(etiquettes)
    n, k = len(etiquettes), len(compte)
    return {c: math.sqrt(n / (k * v)) for c, v in compte.items()}


def lignes_audit(chemin: Path) -> list[tuple[str, str, str]]:
    """(groupe, texte, catégorie). Montants déjà en convention FEC."""
    lignes = []
    with chemin.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["categorie"] in EXCLUES or not row["libelle_bancaire"].strip():
                continue
            if row.get("type_transaction") == "composite":
                continue
            try:
                montant = float(row["montant"])
            except ValueError:
                continue
            lignes.append((row["dossier_id"], texte(row["libelle_bancaire"], montant), row["categorie"]))
    return lignes


def lignes_decisions() -> list[tuple[str, str, str]]:
    """Dernière décision humaine de chaque écriture, hors dossiers de démo.
    Le montant bancaire (encaissement positif) est retourné en convention FEC."""
    import os

    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    engine = create_engine(os.environ["DATABASE_URL"])
    requete = text(
        """
        SELECT DISTINCT ON (d.ecriture_id) d.dossier_id, e.libelle, d.categorie,
          (SELECT SUM(CASE WHEN l.sens = 'DEBIT' THEN l.montant_centimes
                           ELSE -l.montant_centimes END)
             FROM lignes_ecriture l
            WHERE l.ecriture_id = e.id AND l.compte LIKE '512%') AS montant_bancaire_cts
        FROM decisions_humaines d JOIN ecritures e ON e.id = d.ecriture_id
        WHERE d.dossier_id NOT LIKE 'DEMO\\_%'
        ORDER BY d.ecriture_id, d.decide_le DESC
        """
    )
    lignes = []
    with engine.connect() as connexion:
        for dossier_id, libelle, categorie, montant_cts in connexion.execute(requete):
            if montant_cts is None:
                continue
            libelle = _SUFFIXE_CATEGORIE.sub("", libelle)
            categorie = CATEGORIE_DECISION_VERS_TAXONOMIE.get(categorie, categorie)
            lignes.append((f"app:{dossier_id}", texte(libelle, -montant_cts / 100), categorie))
    return lignes


def pipeline(etiquettes: list[str]) -> Pipeline:
    return Pipeline(
        [
            # n-grammes de caractères : libellés courts, tronqués et bruités ; le
            # token [M+3] reste intact grâce à char_wb.
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2)),
            ("clf", LogisticRegression(max_iter=1000, class_weight=poids_racine(etiquettes))),
        ]
    )


@dataclass
class HorsEchantillon:
    """Prédictions de la validation croisée : chaque ligne prédite par un
    modèle qui n'a pas vu son dossier."""

    predites: np.ndarray
    confiances: np.ndarray
    justes: np.ndarray
    plis: np.ndarray


def hors_echantillon(groupes: np.ndarray, x: np.ndarray, y: np.ndarray) -> HorsEchantillon:
    predites = np.empty(len(y), dtype=object)
    confiances = np.zeros(len(y))
    plis = np.zeros(len(y), dtype=int)
    for pli, (entrainement, test) in enumerate(GroupKFold(PLIS).split(x, y, groupes)):
        modele = pipeline(list(y[entrainement])).fit(x[entrainement], y[entrainement])
        probabilites = modele.predict_proba(x[test])
        predites[test] = modele.classes_[probabilites.argmax(1)]
        confiances[test] = probabilites.max(1)
        plis[test] = pli
    return HorsEchantillon(predites, confiances, predites == y, plis)


def calibrateur(confiances: np.ndarray, justes: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(confiances, justes)


def classes_imputables(predites: np.ndarray, calibrees: np.ndarray, justes: np.ndarray) -> list[str]:
    admises = []
    for classe in sorted(set(predites)):
        if classe in JAMAIS_IMPUTEES or classe.startswith("a_verifier"):
            continue
        garde = (predites == classe) & (calibrees >= SEUIL_IMPUTATION)
        if garde.sum() >= SUPPORT_IMPUTATION and justes[garde].mean() >= PRECISION_IMPUTATION:
            admises.append(classe)
    return admises


def erreur_calibration(probabilites: np.ndarray, justes: np.ndarray, tranches: int = 10) -> float:
    """ECE : écart moyen, pondéré, entre confiance annoncée et justesse réelle."""
    indices = np.minimum((probabilites * tranches).astype(int), tranches - 1)
    return float(
        sum(
            (indices == i).mean() * abs(probabilites[indices == i].mean() - justes[indices == i].mean())
            for i in range(tranches)
            if (indices == i).any()
        )
    )


def evaluer_calibration(oof: HorsEchantillon) -> list[str]:
    """Validation croisée imbriquée : calibration et classes admises choisies
    sur 4 plis, mesurées sur le 5e."""
    calibrees = np.zeros(len(oof.justes))
    imputees = np.zeros(len(oof.justes), dtype=bool)
    for pli in range(PLIS):
        appris, mesure = oof.plis != pli, oof.plis == pli
        iso = calibrateur(oof.confiances[appris], oof.justes[appris])
        calibrees[mesure] = iso.predict(oof.confiances[mesure])
        admises = set(
            classes_imputables(oof.predites[appris], iso.predict(oof.confiances[appris]), oof.justes[appris])
        )
        imputees[mesure] = (calibrees[mesure] >= SEUIL_IMPUTATION) & np.isin(
            oof.predites[mesure], list(admises)
        )
    proposees = calibrees >= SEUIL_PROPOSITION
    return [
        "",
        "Calibration (validation croisée imbriquée) :",
        (
            f"  erreur de calibration (ECE) brute {erreur_calibration(oof.confiances, oof.justes):.3f}"
            f" -> calibrée {erreur_calibration(calibrees, oof.justes):.3f}"
        ),
        (
            f"  proposition (calibrée >= {SEUIL_PROPOSITION}) : {proposees.mean() * 100:.1f} % des"
            f" lignes, justes à {oof.justes[proposees].mean() * 100:.1f} %"
        ),
        (
            f"  imputation automatique (calibrée >= {SEUIL_IMPUTATION}, classes admises) :"
            f" {imputees.mean() * 100:.1f} % des lignes, justes à"
            f" {oof.justes[imputees].mean() * 100:.1f} %"
        ),
    ]


def evaluer(groupes: np.ndarray, y: np.ndarray, oof: HorsEchantillon) -> list[str]:
    predites, confiances, justes = oof.predites, oof.confiances, oof.justes
    rapport = [
        f"Exactitude (validation croisée {PLIS} plis par dossier) : {justes.mean() * 100:.1f} %",
        f"Rappel moyen par classe : {balanced_accuracy_score(y, predites) * 100:.1f} %",
        "",
        "Seuil de confiance | lignes proposées | justes parmi elles",
    ]
    for seuil in SEUILS:
        garde = confiances >= seuil
        rapport.append(
            f"  {seuil:.1f}             | {garde.mean() * 100:5.1f} %          | "
            f"{justes[garde].mean() * 100:5.1f} %"
        )
    rapport += ["", "Rappel par classe (n) :"]
    for classe, n in sorted(Counter(y).items(), key=lambda c: -c[1]):
        masque = y == classe
        rapport.append(f"  {classe:40s} {n:6d}  {justes[masque].mean() * 100:5.1f} %")
    if any(g.startswith("app:") for g in groupes):
        masque = np.array([g.startswith("app:") for g in groupes])
        rapport += [
            "",
            (
                f"Décisions de l'application : {masque.sum()} lignes, "
                f"exactitude sur elles {justes[masque].mean() * 100:.1f} %"
            ),
        ]
    return rapport + evaluer_calibration(oof)


def ecrire_calibration(chemin: Path, oof: HorsEchantillon) -> list[str]:
    """Courbe et politique finales, apprises sur toutes les prédictions hors
    échantillon ; lues par `backend/axelcompta/categorize/ml_fallback.py`."""
    iso = calibrateur(oof.confiances, oof.justes)
    admises = classes_imputables(oof.predites, iso.predict(oof.confiances), oof.justes)
    chemin.write_text(
        json.dumps(
            {
                "version": 1,
                "calibration": {
                    "x": [float(v) for v in iso.X_thresholds_],
                    "y": [float(v) for v in iso.y_thresholds_],
                },
                "seuil_proposition": SEUIL_PROPOSITION,
                "seuil_imputation": SEUIL_IMPUTATION,
                "classes_imputables": admises,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return ["", f"Classes imputables automatiquement ({len(admises)}) : {', '.join(admises)}"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entree", type=Path, default=ENTREE)
    parser.add_argument("--modele", type=Path, default=SORTIE_MODELE)
    parser.add_argument("--rapport", type=Path, default=SORTIE_RAPPORT)
    parser.add_argument("--decisions", action="store_true", help="ajoute les décisions en base")
    args = parser.parse_args()

    lignes = lignes_audit(args.entree)
    n_audit = len(lignes)
    if args.decisions:
        lignes += lignes_decisions()
    n_decisions = len(lignes) - n_audit
    compte = Counter(c for _, _, c in lignes)
    ecartees = {c: n for c, n in compte.items() if n < MIN_EXEMPLES_PAR_CLASSE}
    lignes = [ligne for ligne in lignes if ligne[2] not in ecartees]

    groupes = np.array([g for g, _, _ in lignes])
    x = np.array([t for _, t, _ in lignes])
    y = np.array([c for _, _, c in lignes])
    oof = hors_echantillon(groupes, x, y)
    rapport = [
        "Modèle v2 : TF-IDF char 2-4 (libellé + bucket de montant) + LogReg, pondération racine",
        "Labels = mapping compte PCG -> catégorie (+ décisions de l'application), PAS relecture humaine.",
        f"Lignes : {len(lignes)} (avant filtrage : audit {n_audit}, décisions {n_decisions})",
        f"Dossiers : {len(set(groupes))} | classes : {len(set(y))}",
        f"Classes écartées (< {MIN_EXEMPLES_PAR_CLASSE} exemples) : {ecartees}",
        "",
        *evaluer(groupes, y, oof),
    ]

    modele = pipeline(list(y)).fit(x, y)
    args.modele.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, args.modele)
    # AXE-825 : empreinte vérifiée au chargement (`ml_fallback.verifier_empreinte`).
    empreinte = hashlib.sha256(args.modele.read_bytes()).hexdigest()
    args.modele.with_name(args.modele.name + ".sha256").write_text(
        f"{empreinte}  {args.modele.name}\n", encoding="utf-8"
    )
    calibration = args.modele.with_suffix(".calibration.json")
    rapport += ecrire_calibration(calibration, oof)
    args.rapport.write_text("\n".join(rapport) + "\n", encoding="utf-8")
    print("\n".join(rapport[:12]))
    print("\n".join(rapport[-8:]))
    print(f"Modèle -> {args.modele}\nCalibration -> {calibration}\nRapport -> {args.rapport}")


if __name__ == "__main__":
    main()
