"""registres officiels (INSEE, RNE) : lectures, écarts, résolutions

Revision ID: c7e4a9d2f518
Revises: a3f8c2d71e46

AXE-849. Le dossier garde son SIREN (pour relire les registres) et ses
écarts non tranchés (comme `a_confirmer`, la clôture et la liasse les
attendent). Chaque lecture d'un registre est gardée avec sa date ; chaque
écart tranché aussi (qui, quand, quelle valeur retenue). Les deux tables
sont en ajout seul, RLS par dossier.

Le rôle web lit les lectures, enregistre une résolution, et met à jour
`ecarts_registre` (et `forme_juridique` quand la forme du registre est
retenue). Les lectures sont écrites par les tâches planifiées (rôle
propriétaire).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e4a9d2f518"
down_revision: str | Sequence[str] | None = "a3f8c2d71e46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("lectures_registre", "resolutions_ecart")


def _isoler(table: str) -> None:
    op.create_index(f"ix_{table}_dossier_id", table, ["dossier_id"])
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_isolation ON {table}
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {table}_immuables
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def upgrade() -> None:
    op.add_column("dossiers", sa.Column("siren", sa.String(), nullable=True))
    op.add_column(
        "dossiers", sa.Column("ecarts_registre", sa.JSON(), nullable=False, server_default="[]")
    )
    op.create_table(
        "lectures_registre",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("siren", sa.String(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("fiche", sa.JSON(), nullable=False),
        sa.Column("lu_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "resolutions_ecart",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("champ", sa.String(), nullable=False),
        sa.Column("declare", sa.String(), nullable=False),
        sa.Column("officiel", sa.String(), nullable=False),
        sa.Column("retenue", sa.String(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "retenue IN ('declaree', 'officielle')", name="resolutions_ecart_retenue"
        ),
    )
    for table in _TABLES:
        _isoler(table)
    op.execute("GRANT SELECT ON lectures_registre TO axelcompta_web")
    op.execute("GRANT SELECT, INSERT ON resolutions_ecart TO axelcompta_web")
    op.execute("GRANT UPDATE (ecarts_registre, forme_juridique) ON dossiers TO axelcompta_web")


def downgrade() -> None:
    # forme_juridique garde son UPDATE : la confirmation d'AXE-730 en a besoin
    # aussi (migration a3f8c2d71e46 d'AXE-846).
    op.execute("REVOKE UPDATE (ecarts_registre) ON dossiers FROM axelcompta_web")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immuables ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.drop_index(f"ix_{table}_dossier_id", table_name=table)
        op.drop_table(table)
    op.drop_column("dossiers", "ecarts_registre")
    op.drop_column("dossiers", "siren")
