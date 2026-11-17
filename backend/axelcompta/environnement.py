"""Fichiers d'environnement du processus.

`.env` porte les secrets. `.env.dev`, s'il existe, est chargé ensuite et
l'emporte : c'est le fichier du poste de développement. `ENV=dev` y coupe
Sentry (voir `installer_sentry`). Une variable déjà posée par le
processus (Docker, CI) n'est pas écrasée par `.env`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


def racine_depot() -> Path:
    return Path(__file__).resolve().parents[2]


def charger_environnement(racine: Path | None = None) -> None:
    """Charge `.env` puis `.env.dev`. Pendant pytest, le dépôt réel n'est
    pas lu : les tests posent leurs variables eux-mêmes. Un `racine` explicite
    charge quand même (les tests de cette fonction)."""
    if racine is None and "pytest" in sys.modules:
        return
    dossier = racine_depot() if racine is None else racine
    load_dotenv(dossier / ".env")
    developpement = dossier / ".env.dev"
    if developpement.is_file():
        load_dotenv(developpement, override=True)
