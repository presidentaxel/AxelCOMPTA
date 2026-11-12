"""date des propositions de catégorisation

Revision ID: c4e8b2f6a1d7
Revises: f1c7a3e9b2d5
Create Date: 2026-11-12

AXE-900. `propositions_categorisation.cree_le` : le moment où la synchro a
écrit l'opération. Sert au délai opération → écriture imputée (doc 01 §6,
cible < 48 h). Nul pour les propositions plus anciennes, qui sont exclues
de la mesure : leur date est inconnue, rien n'est réécrit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8b2f6a1d7"
down_revision: str | Sequence[str] | None = "f1c7a3e9b2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "propositions_categorisation",
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("propositions_categorisation", "cree_le")
