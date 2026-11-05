"""activité NAF et éléments de configuration à confirmer

Revision ID: d4a8c2e61f37
Revises: b7e1c4a92f30

AXE-834. `code_naf` : activité principale Sirene. `a_confirmer` : éléments
proposés sans certitude (forme SAS/SASU ou SARL/EURL, premier exercice tiré
de la date de création), à confirmer par le dirigeant. Additif.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8c2e61f37"
down_revision: str | Sequence[str] | None = "b7e1c4a92f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dossiers", sa.Column("code_naf", sa.String(), nullable=True))
    op.add_column(
        "dossiers",
        sa.Column("a_confirmer", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("dossiers", "a_confirmer")
    op.drop_column("dossiers", "code_naf")
