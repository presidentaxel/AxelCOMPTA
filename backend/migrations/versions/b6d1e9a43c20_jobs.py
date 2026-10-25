"""jobs : file PostgreSQL SKIP LOCKED (ADR-002).

Le worker (rôle propriétaire) prend les lignes. Le rôle web n'a aucun
droit : la file n'est pas un écran. RLS activé, sans policy, donc
`axelcompta_web` ne voit rien.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6d1e9a43c20"
down_revision: str | Sequence[str] | None = "a8c3e1d94b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("priorite", sa.Integer(), nullable=False),
        sa.Column("tentatives", sa.Integer(), nullable=False),
        sa.Column("verrou_par", sa.String(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("derniere_erreur", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_en_attente", "jobs", ["statut", "priorite", "cree_le"])
    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_jobs_en_attente", table_name="jobs")
    op.drop_table("jobs")
