"""jobs : heure de prise par le worker

Revision ID: d4b7e9a2c361
Revises: c8a4f1d2e7b5

AXE-958. Un job pris par un worker tué en cours de route (redéploiement)
restait `en_cours` pour toujours. `pris_le` permet de le relâcher après un
délai. Les jobs déjà en cours n'ont pas d'heure : le worker retombe sur
`cree_le`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4b7e9a2c361"
down_revision: str | Sequence[str] | None = "c8a4f1d2e7b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("pris_le", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "pris_le")
