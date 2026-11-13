"""origine des liens Rollee, historique et file « à choisir »

Revision ID: e2a6c8f4b913
Revises: d5f9c3a7e2b1
Create Date: 2026-11-13

AXE-911. `utilisateurs_rollee` garde comment le lien a été posé : `cree`
(espace chauffeur, la valeur des lignes existantes), `auto` (rapprochement,
avec l'indice) ou `manuel` (gestionnaire, avec son e-mail).
`liens_rollee_retires` : un lien retiré, jamais effacé (ajout seul).
`rapprochements_rollee` : les users Rollee à choisir ou non trouvés, par
portefeuille, sans aucune donnée en clair.

Le rôle web peut retirer un lien (DELETE), le garder à l'historique, vider
la file après un choix, et marquer « délié » les relevés de l'ancien lien.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a6c8f4b913"
down_revision: str | Sequence[str] | None = "d5f9c3a7e2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "utilisateurs_rollee",
        sa.Column("origine", sa.String(), nullable=False, server_default="cree"),
    )
    op.add_column("utilisateurs_rollee", sa.Column("indice", sa.String(), nullable=True))
    op.add_column("utilisateurs_rollee", sa.Column("relie_par", sa.String(), nullable=True))
    op.create_check_constraint(
        "ck_utilisateurs_rollee_origine",
        "utilisateurs_rollee",
        "origine IN ('cree', 'auto', 'manuel')",
    )
    op.execute("GRANT DELETE ON utilisateurs_rollee TO axelcompta_web")

    op.create_table(
        "liens_rollee_retires",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("rollee_user_id", sa.String(), nullable=False),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("origine", sa.String(), nullable=False),
        sa.Column("indice", sa.String(), nullable=True),
        sa.Column("relie_par", sa.String(), nullable=True),
        sa.Column("relie_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retire_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retire_par", sa.String(), nullable=False),
        sa.Column("motif", sa.String(), nullable=False),
    )
    op.create_index("ix_liens_rollee_retires_dossier_id", "liens_rollee_retires", ["dossier_id"])
    op.execute("ALTER TABLE liens_rollee_retires ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY liens_rollee_retires_isolation ON liens_rollee_retires "
        "FOR ALL TO axelcompta_web "
        "USING (axelcompta_dossier_visible(dossier_id)) "
        "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
    )
    op.execute("GRANT SELECT, INSERT ON liens_rollee_retires TO axelcompta_web")

    op.create_table(
        "rapprochements_rollee",
        sa.Column("rollee_user_id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("etat", sa.String(), nullable=False),
        sa.Column("candidats", sa.JSON(), nullable=False),
        sa.Column("apercu", sa.JSON(), nullable=False),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "etat IN ('a_choisir', 'non_trouve', 'ecarte')", name="ck_rapprochements_rollee_etat"
        ),
    )
    op.create_index("ix_rapprochements_rollee_tenant_id", "rapprochements_rollee", ["tenant_id"])
    op.execute("ALTER TABLE rapprochements_rollee ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rapprochements_rollee_isolation ON rapprochements_rollee "
        "FOR ALL TO axelcompta_web "
        "USING (tenant_id = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, UPDATE, DELETE ON rapprochements_rollee TO axelcompta_web")
    op.execute("GRANT UPDATE ON settlements_plateforme TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE UPDATE ON settlements_plateforme FROM axelcompta_web")
    for table in ("rapprochements_rollee", "liens_rollee_retires"):
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.drop_table(table)
    op.execute("REVOKE DELETE ON utilisateurs_rollee FROM axelcompta_web")
    op.drop_constraint("ck_utilisateurs_rollee_origine", "utilisateurs_rollee")
    for colonne in ("relie_par", "indice", "origine"):
        op.drop_column("utilisateurs_rollee", colonne)
