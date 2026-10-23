"""Env Alembic personnalisé : lit DATABASE_URL (doc 03 §2, .env.example à la
racine du repo) plutôt que la valeur figée dans alembic.ini, et pointe
`target_metadata` sur les tables définies par module (`tenants/orm.py`,
`ledger/orm.py`...) pour que `--autogenerate` fonctionne.
"""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Import les modules qui définissent des tables sur metadata (doc 03 §3) —
# l'import seul suffit à les enregistrer, pas besoin d'utiliser les noms.
import axelcompta.documents.orm  # noqa: F401
import axelcompta.ingestion.orm  # noqa: F401
import axelcompta.ledger.orm  # noqa: F401
import axelcompta.tenants.orm  # noqa: F401
import axelcompta.workflow.orm  # noqa: F401
from axelcompta.core.db import metadata

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _url_depuis_env() -> str:
    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL manquante (voir .env.example à la racine du repo)")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_url_depuis_env(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _url_depuis_env()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
