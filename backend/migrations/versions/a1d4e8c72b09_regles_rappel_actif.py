"""Une règle de rappel peut être suspendue sans être supprimée.

Revision ID: a1d4e8c72b09
Revises: b6d1e9a43c20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d4e8c72b09"
down_revision: str | Sequence[str] | None = "b6d1e9a43c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regles_rappel",
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("regles_rappel", "actif")
