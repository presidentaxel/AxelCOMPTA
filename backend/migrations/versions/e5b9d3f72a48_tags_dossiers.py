"""tags d'entreprises et réglages d'exclusion

Revision ID: e5b9d3f72a48
Revises: d4a8c2e61f37

AXE-829. `tags` par portefeuille ; `evenements_tags` (pose et retrait) et
`reglages_exclusion` sont append-only, verrouillés comme le journal
d'audit : l'état courant est le dernier événement, l'historique est la
trace. RLS par portefeuille (`app.tenant_id`) ; un tag ne se pose que sur un
dossier du même portefeuille.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b9d3f72a48"
down_revision: str | Sequence[str] | None = "d4a8c2e61f37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DU_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"
_DOSSIER_DU_PORTEFEUILLE = (
    "tenant_id = (SELECT d.tenant_id FROM dossiers d WHERE d.id = evenements_tags.dossier_id)"
)


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "nom"),
    )
    op.create_table(
        "evenements_tags",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rang", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("pose", sa.Boolean(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "tag"], ["tags.tenant_id", "tags.nom"]),
    )
    op.create_index("ix_evenements_tags_dossier_id", "evenements_tags", ["dossier_id"])
    op.create_table(
        "reglages_exclusion",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rang", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("traitement", sa.String(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reglages_exclusion_tenant_id", "reglages_exclusion", ["tenant_id"])
    for table in ("tags", "evenements_tags", "reglages_exclusion"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        controle = (
            f"{_DU_PORTEFEUILLE} AND {_DOSSIER_DU_PORTEFEUILLE}"
            if table == "evenements_tags"
            else _DU_PORTEFEUILLE
        )
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
              FOR ALL TO axelcompta_web
              USING ({_DU_PORTEFEUILLE})
              WITH CHECK ({controle})
            """
        )
        op.execute(f"GRANT SELECT, INSERT ON {table} TO axelcompta_web")
    for table in ("evenements_tags", "reglages_exclusion"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_immuables
              BEFORE UPDATE OR DELETE ON {table}
              FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
            """
        )


def downgrade() -> None:
    for table in ("evenements_tags", "reglages_exclusion"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immuables ON {table}")
    for table in ("reglages_exclusion", "evenements_tags", "tags"):
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
    op.drop_index("ix_reglages_exclusion_tenant_id", table_name="reglages_exclusion")
    op.drop_table("reglages_exclusion")
    op.drop_index("ix_evenements_tags_dossier_id", table_name="evenements_tags")
    op.drop_table("evenements_tags")
    op.drop_table("tags")
