"""Les migrations Alembic contre un vrai Postgres (AXE-854).

Avant, ce test vérifiait 8 tables écrites à la main sur 37. Une migration
qui oubliait une table, une colonne, ou ne la retirait pas au `downgrade`
passait. Désormais la référence est le modèle ORM (`core.db.metadata`) :

* après `upgrade head`, le schéma des migrations et le modèle ORM ont les
  mêmes tables et les mêmes colonnes (comparaison d'Alembic, comme
  `alembic check`), à des écarts près, listés et expliqués ici ;
* la RLS est active sur toute table qui porte `dossier_id` ou `tenant_id` ;
* après `downgrade base`, il ne reste aucune table.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import SchemaItem

# Enregistre chaque table dans `metadata`, comme `migrations/env.py`.
import axelcompta.anomaly.orm  # noqa: F401
import axelcompta.documents.orm  # noqa: F401
import axelcompta.ingestion.orm  # noqa: F401
import axelcompta.ledger.orm  # noqa: F401
import axelcompta.tenants.orm  # noqa: F401
import axelcompta.workflow.orm  # noqa: F401
from axelcompta.core.db import metadata

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parent.parent.parent

# Tables posées par Alembic seulement, sans modèle ORM.
TABLES_HORS_ORM = {
    "alembic_version": "tenue par Alembic lui-même",
    "jobs": "file de jobs (ADR-002), lue en SQL par `jobs/postgres.py`",
}

# Écarts voulus entre le schéma des migrations et le modèle ORM. Les tests
# créent leurs tables par `metadata.create_all`, sans le trigger qui pose ces
# colonnes : elles y restent nullables. En base, le trigger
# `ecritures_numerotation` (I3, migration a3e8c1f5b297) les remplit toujours.
ECARTS_VOULUS = {
    ("modify_nullable", "ecritures", "numero"),
    ("modify_nullable", "ecritures", "exercice_debut"),
    ("modify_nullable", "ecritures", "valide_le"),
    ("remove_constraint", "ecritures", "dossier_id,exercice_debut,numero"),
}


def _config() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _hors_orm(objet: SchemaItem, nom: str | None, type_: str, *_: Any) -> bool:
    """Écarte de la comparaison les tables sans modèle, et leurs index."""
    table = nom if type_ == "table" else getattr(getattr(objet, "table", None), "name", None)
    return table not in TABLES_HORS_ORM


def _cle(ecart: Any) -> tuple[str, ...]:
    """Une clé lisible par écart : (genre, table, détail)."""
    if isinstance(ecart, list):  # modifications de colonne, groupées par Alembic
        ecart = ecart[0]
    genre = ecart[0]
    if genre == "modify_nullable":
        return (genre, ecart[2], ecart[3])
    objet = ecart[1]
    if genre in ("add_table", "remove_table"):
        return (genre, objet.name)
    if genre in ("add_column", "remove_column"):
        return (genre, ecart[2], ecart[3].name)
    table = objet.table.name if getattr(objet, "table", None) is not None else "?"
    colonnes = ",".join(sorted(c.name for c in getattr(objet, "columns", ())))
    return (genre, table, colonnes)


def _ecarts(engine: Engine) -> set[tuple[str, ...]]:
    with engine.connect() as connexion:
        contexte = MigrationContext.configure(
            connexion, opts={"include_object": _hors_orm, "compare_type": True}
        )
        return {_cle(ecart) for ecart in compare_metadata(contexte, metadata)}


def _tables_sans_rls(engine: Engine, tables: Iterable[str]) -> set[str]:
    with engine.connect() as connexion:
        actives = {
            nom
            for (nom,) in connexion.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity"
                )
            )
        }
    return set(tables) - actives


def test_upgrade_head_donne_le_schema_du_modele(engine: Engine) -> None:
    """Supprimer une table, une colonne ou en ajouter une sans migration
    fait échouer ce test, avec l'écart en clair."""
    command.upgrade(_config(), "head")

    en_base = set(inspect(engine).get_table_names())
    assert en_base - set(metadata.tables) == set(TABLES_HORS_ORM)
    assert _ecarts(engine) == ECARTS_VOULUS


def test_la_rls_est_active_sur_chaque_table_de_dossier_ou_de_portefeuille(
    engine: Engine,
) -> None:
    command.upgrade(_config(), "head")
    inspecteur = inspect(engine)
    concernees = {
        table
        for table in inspecteur.get_table_names()
        if {"dossier_id", "tenant_id"} & {c["name"] for c in inspecteur.get_columns(table)}
    }

    assert len(concernees) > 25  # garde-fou : la requête a bien lu le schéma
    assert _tables_sans_rls(engine, concernees) == set()


def test_downgrade_base_ne_laisse_aucune_table(engine: Engine) -> None:
    cfg = _config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "base")

    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()
