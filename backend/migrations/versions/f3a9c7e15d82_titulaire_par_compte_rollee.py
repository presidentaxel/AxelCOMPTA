"""titulaire de chaque compte Rollee

Revision ID: f3a9c7e15d82
Revises: e7c3a9b41d28

Un user Rollee peut porter les comptes de plusieurs chauffeurs. Le lien
garde les empreintes de nom du dossier (`noms_attendus`, NULL pour un user
créé depuis son espace : tous ses comptes sont à lui). Chaque compte de
plateforme dit s'il est retenu, ou s'il est au nom d'un autre chauffeur.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a9c7e15d82"
down_revision: str | Sequence[str] | None = "e7c3a9b41d28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("utilisateurs_rollee", sa.Column("noms_attendus", sa.JSON(), nullable=True))
    op.add_column(
        "comptes_rollee",
        sa.Column("retenu", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "comptes_rollee",
        sa.Column("titulaire_autre", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("comptes_rollee", "titulaire_autre")
    op.drop_column("comptes_rollee", "retenu")
    op.drop_column("utilisateurs_rollee", "noms_attendus")
