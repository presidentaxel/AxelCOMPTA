"""le rôle web lit la révision du schéma

Revision ID: f2b7c5d93a18
Revises: b5f2d8a6c413

AXE-841 : l'API (rôle `axelcompta_web`) vérifie au démarrage que la base
est à la révision du code. Lecture seule, rien d'autre.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2b7c5d93a18"
down_revision: str | Sequence[str] | None = "b5f2d8a6c413"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON alembic_version TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON alembic_version FROM axelcompta_web")
