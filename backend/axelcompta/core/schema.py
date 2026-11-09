"""Le schéma de la base est-il celui que le code attend ? (AXE-841)

Deux garde-fous :

* **une seule tête Alembic** : deux migrations qui partent de la même
  révision ouvrent deux têtes, et `alembic upgrade head` échoue en
  production. Un test le vérifie à chaque CI ;
* **l'API refuse de démarrer sur une base en retard** : un code plus récent
  que la base répond 500 dès qu'il touche une table absente (vu le 6 nov.
  sur `/expert/classees`). Mieux vaut ne pas démarrer, avec la commande à
  lancer.

`AXELCOMPTA_SCHEMA_NON_VERIFIE=1` saute la vérification (poste de dev, pas
la production).
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

DOSSIER_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
VARIABLE_SANS_VERIFICATION = "AXELCOMPTA_SCHEMA_NON_VERIFIE"


class SchemaEnRetard(RuntimeError):
    """La base n'est pas à la révision que le code attend."""


class PlusieursTetes(RuntimeError):
    """Deux migrations partent de la même révision."""


def _scripts(dossier: Path) -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(dossier))
    return ScriptDirectory.from_config(config)


def tete_unique(dossier: Path = DOSSIER_MIGRATIONS) -> str:
    """La révision attendue par le code. Lève `PlusieursTetes` en disant
    quelles migrations rebrancher."""
    scripts = _scripts(dossier)
    tetes = sorted(scripts.get_heads())
    if len(tetes) == 1:
        return tetes[0]
    details = ", ".join(
        f"{tete} (part de {scripts.get_revision(tete).down_revision})" for tete in tetes
    )
    raise PlusieursTetes(
        f"{len(tetes)} têtes Alembic : {details}. Rebrancher le `down_revision` de la "
        "plus récente sur l'autre tête, puis relancer."
    )


def revision_en_base(engine: Engine) -> str | None:
    """`None` si la base n'a jamais été migrée."""
    with engine.connect() as connexion:
        try:
            return connexion.execute(text("SELECT version_num FROM alembic_version")).scalar()
        except ProgrammingError:
            return None


def verifier_schema(engine: Engine, attendue: str) -> None:
    en_base = revision_en_base(engine)
    if en_base != attendue:
        raise SchemaEnRetard(
            f"Base à la révision {en_base or 'aucune'}, code à {attendue} : "
            "lancer `alembic upgrade head` avant de démarrer l'API."
        )


def verification_demandee() -> bool:
    return os.environ.get(VARIABLE_SANS_VERIFICATION) != "1"
