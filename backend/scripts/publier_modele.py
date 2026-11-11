"""Publie une version du modèle de catégorisation dans le bucket privé (AXE-847).

Après `_AUDIT_DONNEES/entrainer_modele.py` (qui écrit le `.joblib`, son
`.sha256` et sa calibration), et **après accord** sur le rapport : la version
part dans le stockage, d'où le worker, la synchro et l'API la récupèrent.

Simulation par défaut : affiche ce qui partirait. `--publier` envoie. Une
version déjà publiée ne se remplace pas : entraîner sous un nouveau nom
(`--modele modeles/tfidf_logreg_v3.joblib`), puis régler
`AXELCOMPTA_MODELE_VERSION`.

Usage, depuis backend/ (S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY dans
l'environnement, voir .env.example) :

    python scripts/publier_modele.py tfidf_logreg_v2
    python scripts/publier_modele.py tfidf_logreg_v2 \\
        --rapport ../_AUDIT_DONNEES/resultats/rapport_modele_v2.txt --publier
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from axelcompta.modeles_distants import a_publier, depot_depuis_env, publier


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("version", help="nom du modèle sans extension (tfidf_logreg_v2)")
    parseur.add_argument("--rapport", type=Path, help="rapport d'entraînement à joindre")
    parseur.add_argument("--publier", action="store_true", help="envoie (sinon simulation)")
    args = parseur.parse_args()

    envoi = a_publier(args.version, rapport=args.rapport)
    for cle, chemin in envoi.items():
        print(f"{cle}  <-  {chemin}")
    if not args.publier:
        print("Simulation : rien n'est envoyé. Relancer avec --publier.")
        return 0
    depot = depot_depuis_env()
    if depot is None:
        print(
            "Stockage S3 non configuré (S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY).",
            file=sys.stderr,
        )
        return 1
    publier(args.version, depot, envoi)
    print(f"Version {args.version} publiée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
