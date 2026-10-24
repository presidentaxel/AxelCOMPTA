"""justificatifs photo, par tenant

Revision ID: a8c3e1d94b20
Revises: c4e8a1b92d06

Le stockage sort de demo_justificatifs.py. Une ligne appartient à un
tenant et à un dossier. La policy reprend axelcompta_dossier_visible et
vérifie que tenant_id est celui du dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c3e1d94b20"
down_revision: str | Sequence[str] | None = "c4e8a1b92d06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "justificatifs",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("ecriture_id", sa.String(), nullable=False),
        sa.Column("empreinte", sa.String(), nullable=False),
        sa.Column("extension", sa.String(), nullable=False),
        sa.Column("taille_octets", sa.Integer(), nullable=False),
        sa.Column("contenu", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "dossier_id", "ecriture_id", name="justificatifs_clef"),
        sa.CheckConstraint("taille_octets > 0", name="justificatifs_taille"),
    )
    op.execute("ALTER TABLE justificatifs ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY justificatifs_isolation ON justificatifs
          FOR ALL TO axelcompta_web
          USING (
            axelcompta_dossier_visible(dossier_id)
            AND tenant_id = (SELECT d.tenant_id FROM dossiers d WHERE d.id = justificatifs.dossier_id)
          )
          WITH CHECK (
            axelcompta_dossier_visible(dossier_id)
            AND tenant_id = (SELECT d.tenant_id FROM dossiers d WHERE d.id = justificatifs.dossier_id)
          )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON justificatifs TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON justificatifs FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS justificatifs_isolation ON justificatifs")
    op.execute("ALTER TABLE justificatifs DISABLE ROW LEVEL SECURITY")
    op.drop_table("justificatifs")
