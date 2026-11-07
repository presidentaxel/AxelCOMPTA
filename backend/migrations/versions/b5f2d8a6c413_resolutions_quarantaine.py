"""résolutions des entrées de quarantaine d'ingestion

Revision ID: b5f2d8a6c413
Revises: a3e8c1f5b297

AXE-424. Une résolution par entrée (accepter / ignorer), avec son auteur
et les écritures passées. Append-only, RLS par dossier. Le rôle web lit
la quarantaine.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5f2d8a6c413"
down_revision: str | Sequence[str] | None = "a3e8c1f5b297"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resolutions_quarantaine",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("entree_id", sa.String(), nullable=False, unique=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("ecritures", sa.JSON(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('accepter', 'ignorer')", name="resolutions_quarantaine_decision"
        ),
    )
    op.create_index(
        "ix_resolutions_quarantaine_dossier_id", "resolutions_quarantaine", ["dossier_id"]
    )
    op.execute("ALTER TABLE resolutions_quarantaine ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY resolutions_quarantaine_isolation ON resolutions_quarantaine
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT ON resolutions_quarantaine TO axelcompta_web")
    # La quarantaine a sa policy depuis 87fc7238e52e, mais aucune route ne la
    # lisait : le gestionnaire la voit maintenant (lecture seule).
    op.execute("GRANT SELECT ON quarantaine_ingestion TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER resolutions_quarantaine_immuables
        BEFORE UPDATE OR DELETE ON resolutions_quarantaine
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS resolutions_quarantaine_immuables ON resolutions_quarantaine"
    )
    op.execute(
        "DROP POLICY IF EXISTS resolutions_quarantaine_isolation ON resolutions_quarantaine"
    )
    op.execute("REVOKE SELECT ON quarantaine_ingestion FROM axelcompta_web")
    op.execute("REVOKE ALL ON resolutions_quarantaine FROM axelcompta_web")
    op.drop_index("ix_resolutions_quarantaine_dossier_id", table_name="resolutions_quarantaine")
    op.drop_table("resolutions_quarantaine")
