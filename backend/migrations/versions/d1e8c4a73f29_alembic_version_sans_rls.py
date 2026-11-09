"""alembic_version lisible par le rôle web

Revision ID: d1e8c4a73f29
Revises: f2b7c5d93a18

AXE-841 : `GRANT SELECT` ne suffit pas. Sur Supabase la sécurité par ligne
est active sur `alembic_version` et aucune règle ne laisse passer
`axelcompta_web`. La lecture revient vide, et l'API refuse de démarrer en
croyant la base jamais migrée. Cette table ne porte aucune donnée de
dossier : la sécurité par ligne n'a rien à y protéger.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d1e8c4a73f29"
down_revision: str | Sequence[str] | None = "f2b7c5d93a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")
