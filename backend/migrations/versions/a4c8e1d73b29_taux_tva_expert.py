"""taux de TVA retenus par l'expert

Revision ID: a4c8e1d73b29
Revises: b6e2d8f1c093

AXE-925. Une ligne (cette écriture) ou un libellé (apprentissage). Le taux
se remplace : ce n'est pas une écriture comptable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c8e1d73b29"
down_revision: str | Sequence[str] | None = "b6e2d8f1c093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taux_tva_expert",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("cle", sa.String(), nullable=False),
        sa.Column("taux", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "dossier_id", "cle"),
        sa.CheckConstraint("taux IN ('20', '10', '5.5', '2.1', '0')", name="taux_tva_expert_taux"),
    )
    op.execute("ALTER TABLE taux_tva_expert ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE taux_tva_expert FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY taux_tva_expert_isolation ON taux_tva_expert
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON taux_tva_expert TO axelcompta_web")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS taux_tva_expert_isolation ON taux_tva_expert")
    op.execute("REVOKE ALL ON taux_tva_expert FROM axelcompta_web")
    op.drop_table("taux_tva_expert")
