"""verdicts sur les classements (juste / faux)

Revision ID: b3d8f1a6c924
Revises: a9c4e7b2d815

AXE-823. Sans écriture : sert à mesurer la précision du classement.
Append-only, RLS par dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d8f1a6c924"
down_revision: str | Sequence[str] | None = "a9c4e7b2d815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verdicts_classement",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rang", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("ecriture_id", sa.String(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("verdict IN ('juste', 'faux')", name="verdicts_classement_valeur"),
    )
    op.create_index("ix_verdicts_classement_dossier_id", "verdicts_classement", ["dossier_id"])
    op.execute("ALTER TABLE verdicts_classement ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY verdicts_classement_isolation ON verdicts_classement
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT ON verdicts_classement TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER verdicts_classement_immuables
        BEFORE UPDATE OR DELETE ON verdicts_classement
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS verdicts_classement_immuables ON verdicts_classement")
    op.execute("DROP POLICY IF EXISTS verdicts_classement_isolation ON verdicts_classement")
    op.execute("REVOKE ALL ON verdicts_classement FROM axelcompta_web")
    op.drop_index("ix_verdicts_classement_dossier_id", table_name="verdicts_classement")
    op.drop_table("verdicts_classement")
