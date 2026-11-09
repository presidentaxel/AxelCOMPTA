"""journal du portefeuille : connexions et réinitialisations de MFA

Revision ID: b8e4c2d7a613
Revises: f6c1a8e3b927

AXE-812. `journal_audit` porte un `dossier_id` obligatoire : il trace ce qui
arrive à un dossier. Une connexion de gestionnaire, ou la réinitialisation
de la double authentification d'un membre, concerne le portefeuille, pas un
dossier. Même principe que `journal_audit` : ajout seul (trigger), RLS par
portefeuille, le rôle web lit et ajoute.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c2d7a613"
down_revision: str | Sequence[str] | None = "f6c1a8e3b927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "journal_portefeuille",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("type_acte", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("acteur", sa.String(), nullable=False),
        sa.Column("acte_le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_portefeuille_tenant_id"), "journal_portefeuille", ["tenant_id"]
    )
    op.execute("ALTER TABLE journal_portefeuille ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY journal_portefeuille_isolation ON journal_portefeuille
          FOR ALL TO axelcompta_web
          USING (tenant_id = current_setting('app.tenant_id', true))
          WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute("GRANT SELECT, INSERT ON journal_portefeuille TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER journal_portefeuille_immuable
        BEFORE UPDATE OR DELETE ON journal_portefeuille
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS journal_portefeuille_immuable ON journal_portefeuille")
    op.execute("REVOKE ALL ON journal_portefeuille FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS journal_portefeuille_isolation ON journal_portefeuille")
    op.drop_index(op.f("ix_journal_portefeuille_tenant_id"), table_name="journal_portefeuille")
    op.drop_table("journal_portefeuille")
