"""cache des opérations déjà classées, par dossier

Revision ID: e9c2a7f14b63
Revises: d8f3b6a1e520

AXE-824. GET /expert/classees reconstruisait le grand livre de chaque
dossier à chaque filtre (environ 12 s sur le portefeuille réel). Les
opérations sont gardées avec la version de `agregats_dossier`, déjà montée
par une écriture ou une décision. Le verdict « juste » / « faux » n'est pas
dans cette table : il change sans écriture.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9c2a7f14b63"
down_revision: str | Sequence[str] | None = "d8f3b6a1e520"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "classees_dossier",
        sa.Column(
            "dossier_id",
            sa.String(),
            sa.ForeignKey("dossiers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("version_source", sa.Integer(), nullable=False),
        sa.Column("version_calcul", sa.Integer(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("calcule_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE classees_dossier ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY classees_dossier_isolation ON classees_dossier
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON classees_dossier TO axelcompta_web")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS classees_dossier_isolation ON classees_dossier")
    op.execute("REVOKE ALL ON classees_dossier FROM axelcompta_web")
    op.drop_table("classees_dossier")
