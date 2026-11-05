"""comptes bancaires d'un dossier et leur sous-compte 512x

Revision ID: c3f7a2e81d45
Revises: b7e1c4a92f30

AXE-832. Une ligne par compte bancaire du dossier chez le fournisseur, avec
son sous-compte de banque (5121, 5122…). Le numéro est unique dans le
dossier et ne change plus. Policy par dossier (axelcompta_dossier_visible) ;
le rôle web lit seulement : l'attribution et le relevé passent par la
synchro, sous la connexion propriétaire.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f7a2e81d45"
down_revision: str | Sequence[str] | None = "b7e1c4a92f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comptes_bancaires",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("identifiant", sa.String(), nullable=False),
        sa.Column("compte_comptable", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("solde_banque_cts", sa.BigInteger(), nullable=True),
        sa.Column("solde_releve_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("dossier_id", "identifiant", name="comptes_bancaires_clef"),
        sa.UniqueConstraint(
            "dossier_id", "compte_comptable", name="comptes_bancaires_compte_unique"
        ),
        sa.CheckConstraint("compte_comptable LIKE '512_%'", name="comptes_bancaires_sous_compte"),
    )
    op.execute("ALTER TABLE comptes_bancaires ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY comptes_bancaires_isolation ON comptes_bancaires
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute("GRANT SELECT ON comptes_bancaires TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON comptes_bancaires FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS comptes_bancaires_isolation ON comptes_bancaires")
    op.execute("ALTER TABLE comptes_bancaires DISABLE ROW LEVEL SECURITY")
    op.drop_table("comptes_bancaires")
