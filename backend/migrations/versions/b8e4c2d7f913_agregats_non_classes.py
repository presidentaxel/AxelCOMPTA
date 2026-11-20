"""AXE-1013 : sous le CA, les charges et le résultat, ce qui attend au 471.

Revision ID: b8e4c2d7f913
Revises: a3d9e6f1c204
Create Date: 2026-11-19

Deux colonnes de plus dans `agregats_dossier`. Le rôle web a déjà SELECT,
INSERT et UPDATE sur toute la table. Les lignes existantes sont recalculées
au fil des lectures (`VERSION_CALCUL` passe à 2).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c2d7f913"
down_revision: str | Sequence[str] | None = "a3d9e6f1c204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLONNES = ("entrees_non_classees_cts", "sorties_non_classees_cts")


def upgrade() -> None:
    for nom in _COLONNES:
        op.add_column(
            "agregats_dossier",
            sa.Column(nom, sa.BigInteger(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for nom in _COLONNES:
        op.drop_column("agregats_dossier", nom)
