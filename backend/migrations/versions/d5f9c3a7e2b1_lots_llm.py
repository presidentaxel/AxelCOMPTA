"""lots envoyés au LLM et alertes de budget

Revision ID: d5f9c3a7e2b1
Revises: c4e8b2f6a1d7
Create Date: 2026-11-13

AXE-887. `lots_llm` : une requête de l'API Batch, ses libellés normalisés,
son statut et son coût (jetons et dollars). Base du budget mensuel, des
nouvelles tentatives et de l'idempotence (l'identifiant est une empreinte
du dossier, de la version, des libellés et de la tentative).
`alertes_llm` : une alerte de budget déjà envoyée, une fois par portée, par
mois et par seuil. Le rôle web lit le nombre de libellés de son
portefeuille (ligne d'Intégrations) ; seules les tâches planifiées écrivent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5f9c3a7e2b1"
down_revision: str | Sequence[str] | None = "c4e8b2f6a1d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lots_llm",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("modele", sa.String(), nullable=False),
        sa.Column("cles", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("estimation_usd", sa.Float(), nullable=False),
        sa.Column("soumis_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.Column("cout_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("jetons_entree", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jetons_sortie", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jetons_cache", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("termine_le", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "statut IN ('soumis', 'termine', 'echec', 'refus')", name="ck_lots_llm_statut"
        ),
    )
    op.create_index("ix_lots_llm_soumis_le", "lots_llm", ["soumis_le"])
    op.execute("ALTER TABLE lots_llm ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY lots_llm_isolation ON lots_llm FOR ALL TO axelcompta_web "
        "USING (tenant_id = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT ON lots_llm TO axelcompta_web")
    op.create_table(
        "alertes_llm",
        sa.Column("portee", sa.String(), primary_key=True),
        sa.Column("cle", sa.String(), primary_key=True),
        sa.Column("mois", sa.String(), primary_key=True),
        sa.Column("seuil", sa.String(), primary_key=True),
        sa.Column("envoyee_le", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alertes_llm")
    op.execute("REVOKE ALL ON lots_llm FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS lots_llm_isolation ON lots_llm")
    op.drop_index("ix_lots_llm_soumis_le", table_name="lots_llm")
    op.drop_table("lots_llm")
