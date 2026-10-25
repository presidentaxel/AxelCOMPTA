"""Fixtures des tests d'intégration (doc 09 §4) : nécessitent un vrai
Postgres — `docker compose up -d db` depuis backend/ (doc 17 semaine 0).
Exclus de la suite rapide par défaut (voir addopts, pyproject.toml).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

# L'import seul enregistre les tables de chaque module sur metadata partagée
# (doc 03 §3) : nécessaire pour que create_all/drop_all les voient.
import axelcompta.documents.orm  # noqa: F401
import axelcompta.ingestion.orm  # noqa: F401
import axelcompta.ledger.orm  # noqa: F401
import axelcompta.tenants.orm  # noqa: F401
import axelcompta.workflow.orm  # noqa: F401
from axelcompta.core.db import engine_depuis_env, metadata
from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.repository import PostgresLedgerService
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.postgres import PostgresDossierRepository

HOTES_LOCAUX = frozenset({"localhost", "127.0.0.1", "::1", "db"})


@pytest.fixture
def engine() -> Iterator[Engine]:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL non définie — voir backend/README.md")
    moteur = engine_depuis_env()
    # Ces tests vident toutes les tables (drop_all) : jamais sur la base
    # Supabase de la démo (ADR-003, 2026-09-24), seulement un Postgres local.
    if moteur.url.host not in HOTES_LOCAUX:
        moteur.dispose()
        pytest.exit(
            f"tests d'intégration refusés sur une base non locale ({moteur.url.host}) : "
            "ils suppriment toutes les tables. Voir backend/README.md.",
            returncode=2,
        )
    yield moteur
    # `jobs` vient d'Alembic et référence `tenants`, sans être dans
    # `metadata`. drop_all échoue sur tenants tant que cette clé étrangère
    # existe, et le test suivant retrouve les lignes du précédent.
    with moteur.begin() as connexion:
        connexion.execute(text("DROP TABLE IF EXISTS jobs"))
    metadata.drop_all(moteur)  # nettoyage après chaque test, no-op si rien à supprimer
    # `alembic_version` n'est pas dans `metadata` (bookkeeping propre à
    # Alembic) : sans ce DROP, un test suivant qui utilise Alembic
    # directement (test_migrations.py) croit être déjà à `head` et ne
    # recrée rien — trouvé le 2026-09-08 en enchaînant plusieurs tests
    # d'intégration dans la même session.
    with moteur.begin() as connexion:
        connexion.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def id_unique() -> str:
    return uuid.uuid4().hex[:12]


@pytest.fixture
def creer_dossier(engine: Engine) -> Callable[[str], None]:
    """Crée un tenant et un dossier : les décisions, propositions et entrées
    du journal ont des clés étrangères vers `dossiers` (migration
    `7cd5053e8209`), on ne peut plus les insérer dans le vide."""

    def _creer(dossier_id: str) -> None:
        metadata.create_all(engine)
        depot = PostgresDossierRepository(engine)
        depot.enregistrer_tenant(Tenant(id=TenantId("t-test"), nom="T"))
        depot.enregistrer(
            Dossier(
                id=DossierId(dossier_id),
                tenant_id=TenantId("t-test"),
                forme_juridique="SASU",
                regime_imposition="IS",
                regime_tva="franchise",
                nom="Test",
                tva_recettes_regime="franchise",
                exercice_debut=date(2026, 1, 1),
            )
        )

    return _creer


@pytest.fixture
def creer_ecriture(engine: Engine) -> Callable[[str, str], None]:
    def _creer(dossier_id: str, ecriture_id: str) -> None:
        montant = Money(1000)
        PostgresLedgerService(engine).enregistrer(
            Ecriture(
                id=EcritureId(ecriture_id),
                dossier_id=DossierId(dossier_id),
                journal=Journal.BQ,
                date=date(2026, 3, 1),
                libelle="test",
                reference_piece=None,
                lignes=(
                    LigneEcriture(compte="512", sens=Sens.CREDIT, montant=montant),
                    LigneEcriture(compte="471", sens=Sens.DEBIT, montant=montant),
                ),
            )
        )

    return _creer
