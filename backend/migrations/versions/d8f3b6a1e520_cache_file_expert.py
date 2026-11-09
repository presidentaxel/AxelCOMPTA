"""cache de la file expert, par dossier

Revision ID: d8f3b6a1e520
Revises: c6e2a9f4b731

AXE-824. Les sujets d'un dossier sont gardés avec la version de
`agregats_dossier` ; ils sont recalculés quand elle bouge. Un justificatif
ajouté ou retiré change les sujets (ticket manquant) : il monte désormais
la version, comme une écriture ou une décision.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f3b6a1e520"
down_revision: str | Sequence[str] | None = "c6e2a9f4b731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_expert_dossier",
        sa.Column(
            "dossier_id",
            sa.String(),
            sa.ForeignKey("dossiers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version_source", sa.Integer(), nullable=False),
        sa.Column("version_calcul", sa.Integer(), nullable=False),
        sa.Column("sujets", sa.JSON(), nullable=False),
        sa.Column("calcule_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE file_expert_dossier ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY file_expert_dossier_isolation ON file_expert_dossier
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON file_expert_dossier TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER justificatifs_perime_agregat
        AFTER INSERT OR DELETE ON justificatifs
        FOR EACH ROW EXECUTE FUNCTION axelcompta_invalider_agregat('dossier_id')
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS justificatifs_perime_agregat ON justificatifs")
    op.execute("DROP POLICY IF EXISTS file_expert_dossier_isolation ON file_expert_dossier")
    op.execute("REVOKE ALL ON file_expert_dossier FROM axelcompta_web")
    op.drop_table("file_expert_dossier")
