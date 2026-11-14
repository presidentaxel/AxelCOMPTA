"""plusieurs comptes Rollee par chauffeur

Revision ID: d2e9c5b81a47
Revises: c1d8e4a72b16

Un chauffeur peut être sur plusieurs comptes Rollee. `rollee_user_id`
reste unique (un compte Rollee, une entreprise). `dossier_id` ne l'est
plus. Chaque plateforme retenue sait de quel compte Rollee elle vient,
pour qu'en retirer un ne vide pas les autres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e9c5b81a47"
down_revision: str | Sequence[str] | None = "c1d8e4a72b16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("utilisateurs_rollee_pkey", "utilisateurs_rollee", type_="primary")
    op.drop_constraint(
        "utilisateurs_rollee_rollee_user_id_key", "utilisateurs_rollee", type_="unique"
    )
    op.create_primary_key("utilisateurs_rollee_pkey", "utilisateurs_rollee", ["rollee_user_id"])
    op.create_index("ix_utilisateurs_rollee_dossier_id", "utilisateurs_rollee", ["dossier_id"])
    op.add_column("comptes_rollee", sa.Column("rollee_user_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("comptes_rollee", "rollee_user_id")
    op.drop_index("ix_utilisateurs_rollee_dossier_id", table_name="utilisateurs_rollee")
    op.drop_constraint("utilisateurs_rollee_pkey", "utilisateurs_rollee", type_="primary")
    op.create_primary_key("utilisateurs_rollee_pkey", "utilisateurs_rollee", ["dossier_id"])
    op.create_unique_constraint(
        "utilisateurs_rollee_rollee_user_id_key", "utilisateurs_rollee", ["rollee_user_id"]
    )
