"""propositions de l'IA par libellé normalisé

Revision ID: a9c2e5f1b7d3
Revises: e8c3a1f6d9b4
Create Date: 2026-11-12

AXE-888. `propositions_ia` : la catégorie proposée par le LLM pour un libellé
normalisé d'un dossier, avec la version du prompt et le modèle. Un libellé
déjà envoyé ne repart jamais. Policy par dossier (`axelcompta_dossier_visible`).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c2e5f1b7d3"
down_revision: str | Sequence[str] | None = "e8c3a1f6d9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "propositions_ia",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), primary_key=True),
        sa.Column("cle", sa.String(), primary_key=True),
        sa.Column("version", sa.String(), primary_key=True),
        sa.Column("categorie", sa.String(), nullable=False),
        sa.Column("confiance", sa.Float(), nullable=False),
        sa.Column("justification", sa.String(), nullable=False),
        sa.Column("modele", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE propositions_ia ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY propositions_ia_isolation ON propositions_ia FOR ALL TO axelcompta_web "
        "USING (axelcompta_dossier_visible(dossier_id)) "
        "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
    )
    op.execute("GRANT SELECT ON propositions_ia TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON propositions_ia FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS propositions_ia_isolation ON propositions_ia")
    op.drop_table("propositions_ia")
