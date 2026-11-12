"""contexte des décisions humaines

Revision ID: f1c7a3e9b2d5
Revises: d8a2c6e4f1b9
Create Date: 2026-11-12

AXE-871. `decisions_humaines.contexte` (JSON) : libellé, montant, moyen de
paiement, proposition en vigueur et nature de la décision (confirmée,
corrigée, sans proposition), tels qu'au moment de décider. Nul pour les
décisions plus anciennes : rien n'est réécrit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1c7a3e9b2d5"
down_revision: str | Sequence[str] | None = "d8a2c6e4f1b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("decisions_humaines", sa.Column("contexte", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions_humaines", "contexte")
