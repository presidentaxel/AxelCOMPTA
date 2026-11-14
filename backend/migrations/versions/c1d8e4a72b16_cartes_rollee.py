"""carte des users Rollee déjà lus

Revision ID: c1d8e4a72b16
Revises: a8d4e2c71b06

Un passage de rapprochement garde l'empreinte de chaque user. Le suivant
compare cette carte sans rappeler le profil ni l'IBAN, et ne lit chez
Rollee que les users absents. Rien en clair : empreintes et aperçu masqué.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d8e4a72b16"
down_revision: str | Sequence[str] | None = "a8d4e2c71b06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cartes_rollee",
        sa.Column("rollee_user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("dossier_metadata", sa.String(), nullable=True),
        sa.Column("empreintes", sa.JSON(), nullable=False),
        sa.Column("apercu", sa.JSON(), nullable=False),
        sa.Column("lu_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("rollee_user_id"),
    )
    op.create_index("ix_cartes_rollee_tenant_id", "cartes_rollee", ["tenant_id"])
    op.execute("ALTER TABLE cartes_rollee ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY cartes_rollee_isolation ON cartes_rollee "
        "FOR ALL TO axelcompta_web "
        "USING (tenant_id = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON cartes_rollee TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON cartes_rollee FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS cartes_rollee_isolation ON cartes_rollee")
    op.drop_index("ix_cartes_rollee_tenant_id", table_name="cartes_rollee")
    op.drop_table("cartes_rollee")
