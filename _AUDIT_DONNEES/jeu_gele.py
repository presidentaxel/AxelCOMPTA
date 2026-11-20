"""Le jeu de test gelé de la catégorisation (AXE-902).

Décision de Louis du 19/11 : le jeu est gelé **sans relecture humaine**. Ses
étiquettes sont celles du mapping compte PCG -> catégorie, comme celles de
l'entraînement. Il mesure donc la généralisation à des dossiers jamais vus,
pas l'exactitude « vraie » (la relecture des 500 lignes d'AXE-423 n'est
pas faite).

Gelé par construction : un dossier en fait partie si l'empreinte de son
identifiant tombe dans les `PART_GELEE` % premiers. La règle ne change pas,
et aucun modèle ne s'entraîne sur ces dossiers (`entrainer_modele.py`).
Le manifeste versionné (`jeu_gele.manifest.json`) garde la liste des
dossiers, le nombre de lignes et l'empreinte du contenu : `--verifier`
signale toute dérive des données.

Usage, depuis _AUDIT_DONNEES/ :

    python jeu_gele.py --entree resultats/fec_ml_taxonomie_v2.csv          # gèle
    python jeu_gele.py --entree resultats/fec_ml_taxonomie_v2.csv --verifier
"""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

PART_GELEE = 15  # % des dossiers
SORTIE = Path("resultats/jeu_gele.csv")
MANIFESTE = Path("jeu_gele.manifest.json")


def est_gele(dossier_id: str) -> bool:
    return int(hashlib.sha256(dossier_id.encode()).hexdigest(), 16) % 100 < PART_GELEE


def lignes_gelees(entree: Path) -> tuple[list[str], list[dict[str, str]]]:
    with entree.open(newline="", encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        lignes = [r for r in lecteur if est_gele(r["dossier_id"])]
        return list(lecteur.fieldnames or []), lignes


def manifeste(entree: Path, lignes: list[dict[str, str]]) -> dict[str, object]:
    empreinte = hashlib.sha256()
    for r in lignes:
        empreinte.update(json.dumps(r, sort_keys=True, ensure_ascii=False).encode())
    return {
        "regle": f"sha256(dossier_id) % 100 < {PART_GELEE}",
        "source": entree.name,
        "etiquettes": "mapping compte PCG -> catégorie, sans relecture humaine (décision du 19/11)",
        "dossiers": sorted({r["dossier_id"] for r in lignes}),
        "lignes": len(lignes),
        "empreinte": empreinte.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entree", type=Path, required=True)
    parser.add_argument("--verifier", action="store_true")
    args = parser.parse_args()

    colonnes, lignes = lignes_gelees(args.entree)
    calcule = manifeste(args.entree, lignes)
    if args.verifier:
        attendu = json.loads(MANIFESTE.read_text(encoding="utf-8"))
        if attendu != calcule:
            print("Le jeu gelé a changé : comparer avec jeu_gele.manifest.json.", file=sys.stderr)
            return 1
        print(f"Jeu gelé intact : {calcule['lignes']} lignes, {len(calcule['dossiers'])} dossiers.")
        return 0
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with SORTIE.open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    MANIFESTE.write_text(json.dumps(calcule, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Gelé : {calcule['lignes']} lignes, {len(calcule['dossiers'])} dossiers -> {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
