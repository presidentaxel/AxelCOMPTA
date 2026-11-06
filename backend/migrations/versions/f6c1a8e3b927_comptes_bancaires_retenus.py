"""comptes bancaires retenus ou écartés par le dirigeant

Revision ID: f6c1a8e3b927
Revises: e9c2a7f14b63

AXE-729. Un contact Digifactory peut avoir un compte personnel à côté du
compte pro : seul le pro doit être comptabilisé.

- `retenu` : NULL à décider, TRUE comptabilisé, FALSE écarté. Les comptes
  déjà enregistrés ont été comptabilisés : ils passent à TRUE.
- `a_relire` : retenu après coup, la prochaine synchro relit l'historique.
- Le rôle web (le dirigeant, depuis l'API) ne modifie que ces deux colonnes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6c1a8e3b927"
down_revision: str | Sequence[str] | None = "e9c2a7f14b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("comptes_bancaires", sa.Column("retenu", sa.Boolean(), nullable=True))
    op.add_column(
        "comptes_bancaires",
        sa.Column("a_relire", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE comptes_bancaires SET retenu = TRUE")
    op.execute("GRANT UPDATE (retenu, a_relire) ON comptes_bancaires TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (retenu, a_relire) ON comptes_bancaires FROM axelcompta_web")
    op.drop_column("comptes_bancaires", "a_relire")
    op.drop_column("comptes_bancaires", "retenu")
