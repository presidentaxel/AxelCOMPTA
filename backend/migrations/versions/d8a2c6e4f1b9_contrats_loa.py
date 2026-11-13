"""contrats de LOA

Revision ID: d8a2c6e4f1b9
Revises: b3f7d1a9c4e2
Create Date: 2026-11-12

AXE-803. `contrats_loa` : la fiche d'un contrat de location avec option
d'achat (loueur, véhicule, durée, loyers, prix de levée, CO2). En ajout seul
pour le rôle web. Policy par dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8a2c6e4f1b9"
down_revision: str | Sequence[str] | None = "b3f7d1a9c4e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contrats_loa",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("loueur", sa.String(), nullable=False),
        sa.Column("vehicule", sa.String(), nullable=False),
        sa.Column("debut", sa.Date(), nullable=False),
        sa.Column("duree_mois", sa.Integer(), nullable=False),
        sa.Column("loyer_mensuel_cts", sa.BigInteger(), nullable=False),
        sa.Column("premier_loyer_cts", sa.BigInteger(), nullable=False),
        sa.Column("prix_levee_cts", sa.BigInteger(), nullable=False),
        sa.Column("co2_g_km", sa.Integer(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_contrats_loa_dossier_id"), "contrats_loa", ["dossier_id"])
    op.execute("ALTER TABLE contrats_loa ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY contrats_loa_isolation ON contrats_loa FOR ALL TO axelcompta_web "
        "USING (axelcompta_dossier_visible(dossier_id)) "
        "WITH CHECK (axelcompta_dossier_visible(dossier_id))"
    )
    op.execute("GRANT SELECT, INSERT ON contrats_loa TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE ALL ON contrats_loa FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS contrats_loa_isolation ON contrats_loa")
    op.drop_index(op.f("ix_contrats_loa_dossier_id"), table_name="contrats_loa")
    op.drop_table("contrats_loa")
