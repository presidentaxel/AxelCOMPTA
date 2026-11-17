"""Le bucket des documents d'import (AXE-970).

Les documents repris d'un chauffeur (FEC, liasses, archives de l'ancien
outil, pièces…) vivent dans un bucket S3 **privé**, à part de celui des
modèles : `DOCUMENTS_BUCKET` (`documents` par défaut), mêmes identifiants
que le stockage des modèles (`S3_ENDPOINT`, `S3_ACCESS_KEY`,
`S3_SECRET_KEY`). Rangement : `tenants.fiches_import.cle_archive`.

Sans stockage configuré (poste de développement, tests), `None` : les
contenus restent en base, comme avant.

Composition root (doc 18) : `tenants` ne connaît que le protocole
`DepotContenus`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache

from axelcompta.modeles_distants import DepotS3, client_s3_depuis_env

BUCKET_DOCUMENTS = "documents"


def depot_documents_depuis_env(environ: Mapping[str, str] | None = None) -> DepotS3 | None:
    valeurs = os.environ if environ is None else environ
    client = client_s3_depuis_env(valeurs)
    if client is None:
        return None
    return DepotS3(client, valeurs.get("DOCUMENTS_BUCKET", "").strip() or BUCKET_DOCUMENTS)


@lru_cache(maxsize=1)
def depot_documents() -> DepotS3 | None:
    """Un seul client par processus."""
    return depot_documents_depuis_env()
