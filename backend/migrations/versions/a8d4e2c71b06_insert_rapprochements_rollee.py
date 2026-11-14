"""le gestionnaire écrit la file « à choisir » de Rollee

Revision ID: a8d4e2c71b06
Revises: e2a6c8f4b913

Le bouton de la fiche rapproche une entreprise. Le rôle web peut alors
ajouter les users « à choisir » ; il pouvait déjà les lire, les modifier
et les retirer.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8d4e2c71b06"
down_revision: str | Sequence[str] | None = "e2a6c8f4b913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT INSERT ON rapprochements_rollee TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE INSERT ON rapprochements_rollee FROM axelcompta_web")
