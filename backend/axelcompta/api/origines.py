"""Origines du navigateur autorisées à appeler l'API.

Le poste de développement reste dans la liste. En production,
``AXELCOMPTA_URL_APP`` (adresse publique du front) et
``AXELCOMPTA_ORIGINES`` (autres origines, séparées par des virgules)
s'y ajoutent. Une origine est le schéma et l'hôte : le chemin est ignoré.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

_ORIGINES_DEV = ("http://localhost:3000", "http://localhost:3001")


def origines_autorisees(environ: Mapping[str, str] | None = None) -> list[str]:
    """Liste sans doublon. Une valeur illisible est ignorée."""
    source = os.environ if environ is None else environ
    brutes = (
        *_ORIGINES_DEV,
        source.get("AXELCOMPTA_URL_APP", ""),
        *source.get("AXELCOMPTA_ORIGINES", "").split(","),
    )
    vues: list[str] = []
    for brute in brutes:
        origine = _origine(brute)
        if origine is not None and origine not in vues:
            vues.append(origine)
    return vues


def _origine(brute: str) -> str | None:
    texte = brute.strip()
    if not texte:
        return None
    morceaux = urlsplit(texte)
    hote = morceaux.hostname
    if morceaux.scheme not in {"http", "https"} or hote is None or hote == "*":
        return None
    if morceaux.username is not None or morceaux.password is not None:
        return None
    if ":" in hote:
        hote = f"[{hote}]"
    port = f":{morceaux.port}" if morceaux.port is not None else ""
    return f"{morceaux.scheme}://{hote}{port}"
