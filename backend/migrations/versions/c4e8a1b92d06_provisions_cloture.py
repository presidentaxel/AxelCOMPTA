"""Estimations de CCA et de FNP saisies avant la clôture.

Revision ID: c4e8a1b92d06
Revises: e2b9d7c41f05

Le chauffeur donne le montant (doc 06 §5 point 5). La liste se remplace
tant que l'exercice est ouvert : ce n'est pas une écriture validée.
La clôture en fait des écritures d'inventaire, qui elles sont immuables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1b92d06"
down_revision: str | Sequence[str] | None = "e2b9d7c41f05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisions_cloture",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("annee", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("nature", sa.String(), nullable=False),
        sa.Column("compte_charge", sa.String(), nullable=False),
        sa.Column("centimes", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("dossier_id", "annee", "position"),
        sa.CheckConstraint("nature IN ('cca', 'fnp')", name="provisions_cloture_nature"),
        sa.CheckConstraint("centimes > 0", name="provisions_cloture_centimes"),
    )
    op.execute("ALTER TABLE provisions_cloture ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY provisions_cloture_isolation ON provisions_cloture
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON provisions_cloture TO axelcompta_web")


def downgrade() -> None:
    op.drop_table("provisions_cloture")
