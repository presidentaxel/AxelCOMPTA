"""Bootstrap SQLAlchemy : métadonnées partagées, moteur (doc 03 §2).

Un seul schéma pour la démo (doc 17 §3) — pas de multi-tenant/RLS ici (ça
viendra en V1, doc 03 §7). Chaque module qui persiste (`tenants`, `ledger`...)
définit ses propres tables sur `metadata`, dans son propre `orm.py`.
"""

from __future__ import annotations

import os

from sqlalchemy import MetaData
from sqlalchemy.engine import Engine, create_engine

metadata = MetaData()

VARIABLE_URL_PAR_DEFAUT = "DATABASE_URL"


def engine_depuis_env(variable: str = VARIABLE_URL_PAR_DEFAUT) -> Engine:
    """Refuse de démarrer avec une config invalide (doc 08 §2.7) : pas de
    valeur par défaut silencieuse, l'URL doit être fournie explicitement
    (voir .env.example à la racine du repo)."""
    url = os.environ.get(variable)
    if not url:
        raise RuntimeError(f"variable d'environnement {variable} manquante (voir .env.example)")
    if "pooler.supabase.com" in url:
        # Session pooler : 15 clients au plus. Le pool SQLAlchemy par défaut
        # (5 permanents + 10 de débordement) les occupe tous, et la requête
        # suivante reçoit EMAXCONNSESSION — l'API répond alors 500.
        return create_engine(url, pool_size=3, max_overflow=4, pool_pre_ping=True)
    return create_engine(url)
