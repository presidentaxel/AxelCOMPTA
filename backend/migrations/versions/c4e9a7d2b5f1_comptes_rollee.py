"""plateformes reliées par le chauffeur dans Rollee

Revision ID: c4e9a7d2b5f1
Revises: b8d4e1f7a2c6
Create Date: 2026-11-11

AXE-819.
- `utilisateurs_rollee` : le « user » Rollee d'un dossier, créé à la
  première demande de connexion, et le branchement qui l'a créé.
- `comptes_rollee` : les comptes de plateformes reliés, relus chez Rollee.
  Aucun montant.
Policy par dossier (`axelcompta_dossier_visible`) : le chauffeur voit les
siens, le gestionnaire ceux de son portefeuille.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e9a7d2b5f1"
down_revision: str | Sequence[str] | None = "b8d4e1f7a2c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("utilisateurs_rollee", "comptes_rollee")


def upgrade() -> None:
    op.create_table(
        "utilisateurs_rollee",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), primary_key=True),
        sa.Column("rollee_user_id", sa.String(), nullable=False, unique=True),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "comptes_rollee",
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("connecte", sa.Boolean(), nullable=False),
        sa.Column("reconnexion", sa.Boolean(), nullable=False),
        sa.Column("relie_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_comptes_rollee_dossier_id"), "comptes_rollee", ["dossier_id"])
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} FOR ALL TO axelcompta_web "
            "USING (axelcompta_dossier_visible(dossier_id)) "
            "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
        )
    op.execute("GRANT SELECT, INSERT ON utilisateurs_rollee TO axelcompta_web")
    op.execute("GRANT SELECT, INSERT, DELETE ON comptes_rollee TO axelcompta_web")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.drop_table(table)
