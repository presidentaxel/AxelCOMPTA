"""annuaire des users Rollee, pour chercher un compte par son nom

Revision ID: f3b7d9e1a2c4
Revises: e2a6c8f4b913
Create Date: 2026-11-14

AXE-919. Le gestionnaire choisit le compte Rollee d'une entreprise en
cherchant son nom parmi tous les users des comptes Rollee du portefeuille.
Nom en clair (décision de Louis du 14/11), e-mail masqué, aucun montant.
Rempli par le passage de rapprochement (connexion propriétaire) ; le rôle
web ne fait que lire, sous la RLS du portefeuille.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b7d9e1a2c4"
down_revision: str | Sequence[str] | None = "e2a6c8f4b913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "annuaire_rollee",
        sa.Column("rollee_user_id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("plateformes", sa.JSON(), nullable=False),
        sa.Column("email_masque", sa.String(), nullable=True),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_annuaire_rollee_tenant_id", "annuaire_rollee", ["tenant_id"])
    op.execute("ALTER TABLE annuaire_rollee ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY annuaire_rollee_isolation ON annuaire_rollee "
        "FOR SELECT TO axelcompta_web "
        "USING (tenant_id = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT ON annuaire_rollee TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON annuaire_rollee FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS annuaire_rollee_isolation ON annuaire_rollee")
    op.drop_table("annuaire_rollee")
