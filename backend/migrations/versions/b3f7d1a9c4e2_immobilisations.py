"""registre des immobilisations et cessions

Revision ID: b3f7d1a9c4e2
Revises: a9c2e5f1b7d3
Create Date: 2026-11-12

AXE-802. `immobilisations` : la fiche d'un bien (compte, mise en service,
base, durée). `cessions_immobilisations` : sa sortie (date, prix). Les deux en
ajout seul : ni UPDATE ni DELETE pour le rôle web. Policy par dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f7d1a9c4e2"
down_revision: str | Sequence[str] | None = "a9c2e5f1b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("immobilisations", "cessions_immobilisations")


def upgrade() -> None:
    op.create_table(
        "immobilisations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("designation", sa.String(), nullable=False),
        sa.Column("compte", sa.String(), nullable=False),
        sa.Column("mise_en_service", sa.Date(), nullable=False),
        sa.Column("base_cts", sa.BigInteger(), nullable=False),
        sa.Column("duree_mois", sa.Integer(), nullable=False),
        sa.Column("ecriture_acquisition", sa.String(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_immobilisations_dossier_id"), "immobilisations", ["dossier_id"])
    op.create_table(
        "cessions_immobilisations",
        sa.Column(
            "immobilisation_id",
            sa.String(),
            sa.ForeignKey("immobilisations.id"),
            primary_key=True,
        ),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("le", sa.Date(), nullable=False),
        sa.Column("prix_cts", sa.BigInteger(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
    )
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_isolation ON {table} FOR ALL TO axelcompta_web "
            "USING (axelcompta_dossier_visible(dossier_id)) "
            "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
        )
        op.execute(f"GRANT SELECT, INSERT ON {table} TO axelcompta_web")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
    op.drop_index(op.f("ix_immobilisations_dossier_id"), table_name="immobilisations")
    op.drop_table("cessions_immobilisations")
    op.drop_table("immobilisations")
