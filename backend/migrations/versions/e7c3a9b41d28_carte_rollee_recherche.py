"""carte Rollee : nombre de comptes, nom et e-mail masqué

Revision ID: e7c3a9b41d28
Revises: d2e9c5b81a47

Un user sans plateforme (`accounts_number` à 0) n'est plus interrogé, et un
user déjà lu n'est relu que si ce nombre change. Le nom en clair et l'e-mail
masqué servent à la recherche du gestionnaire. Aucun montant.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c3a9b41d28"
down_revision: str | Sequence[str] | None = "d2e9c5b81a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cartes_rollee", sa.Column("accounts_number", sa.Integer(), nullable=True))
    op.add_column("cartes_rollee", sa.Column("nom", sa.String(), nullable=True))
    op.add_column("cartes_rollee", sa.Column("email_masque", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("cartes_rollee", "email_masque")
    op.drop_column("cartes_rollee", "nom")
    op.drop_column("cartes_rollee", "accounts_number")
