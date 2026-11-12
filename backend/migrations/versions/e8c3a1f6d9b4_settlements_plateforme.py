"""relevés de revenus des plateformes

Revision ID: e8c3a1f6d9b4
Revises: d6b2f8a4c3e7
Create Date: 2026-11-11

AXE-821. `settlements_plateforme` : une période de revenus d'un compte de
plateforme (Rollee), et son rapprochement avec le virement en banque.
Écrite par le worker (rôle propriétaire) ; lue par le chauffeur du dossier
et le gestionnaire de son portefeuille (policy par dossier).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8c3a1f6d9b4"
down_revision: str | Sequence[str] | None = "d6b2f8a4c3e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settlements_plateforme",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("plateforme", sa.String(), nullable=False),
        sa.Column("periode_debut", sa.Date(), nullable=False),
        sa.Column("periode_fin", sa.Date(), nullable=False),
        sa.Column("verse_le", sa.Date(), nullable=False),
        sa.Column("brut_cts", sa.BigInteger(), nullable=False),
        sa.Column("commission_cts", sa.BigInteger(), nullable=False),
        sa.Column("regime_tva_commission", sa.String(), nullable=False),
        sa.Column("verse_cts", sa.BigInteger(), nullable=False),
        sa.Column("devise", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("etat", sa.String(), nullable=False),
        sa.Column("ecriture_id", sa.String(), nullable=True),
        sa.Column("motif", sa.String(), nullable=True),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_settlements_plateforme_dossier_id"), "settlements_plateforme", ["dossier_id"]
    )
    op.execute("ALTER TABLE settlements_plateforme ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY settlements_plateforme_isolation ON settlements_plateforme FOR ALL "
        "TO axelcompta_web USING (axelcompta_dossier_visible(dossier_id)) "
        "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
    )
    op.execute("GRANT SELECT ON settlements_plateforme TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON settlements_plateforme FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS settlements_plateforme_isolation ON settlements_plateforme")
    op.drop_table("settlements_plateforme")
