"""qualifications d'anomalies en base

Revision ID: a9c4e7b2d815
Revises: f1a6c3e9d257

AXE-814. Avant, en mémoire de process : perdues à chaque redémarrage.
Append-only (verrou `axelcompta_interdire_mutation`), RLS par dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c4e7b2d815"
down_revision: str | Sequence[str] | None = "f1a6c3e9d257"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qualifications_anomalie",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rang", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("alerte_id", sa.String(), nullable=False),
        sa.Column("etat", sa.String(), nullable=False),
        sa.Column("commentaire", sa.Text(), nullable=False),
        sa.Column("acteur", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_qualifications_anomalie_dossier_id", "qualifications_anomalie", ["dossier_id"]
    )
    op.execute("ALTER TABLE qualifications_anomalie ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY qualifications_anomalie_isolation ON qualifications_anomalie
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT, INSERT ON qualifications_anomalie TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER qualifications_anomalie_immuables
        BEFORE UPDATE OR DELETE ON qualifications_anomalie
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS qualifications_anomalie_immuables ON qualifications_anomalie"
    )
    op.execute(
        "DROP POLICY IF EXISTS qualifications_anomalie_isolation ON qualifications_anomalie"
    )
    op.execute("REVOKE ALL ON qualifications_anomalie FROM axelcompta_web")
    op.drop_index("ix_qualifications_anomalie_dossier_id", table_name="qualifications_anomalie")
    op.drop_table("qualifications_anomalie")
