"""paramètres de TVA du dossier : périodicité et jour d'échéance

Revision ID: d4a8f2c6e195
Revises: c9f3a1e6d248

AXE-805. La CA3 se dépose chaque mois ou chaque trimestre, à un jour qui
dépend du SIREN et de la forme (calendrier DGFiP) : deux paramètres du
dossier, vides tant qu'ils ne sont pas réglés. Le dirigeant les règle
depuis son écran « Ma TVA » : le rôle web ne modifie que ces deux colonnes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8f2c6e195"
down_revision: str | Sequence[str] | None = "c9f3a1e6d248"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dossiers", sa.Column("tva_periodicite", sa.String(), nullable=True))
    op.add_column("dossiers", sa.Column("tva_jour_echeance", sa.Integer(), nullable=True))
    op.execute("GRANT UPDATE (tva_periodicite, tva_jour_echeance) ON dossiers TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (tva_periodicite, tva_jour_echeance) ON dossiers FROM axelcompta_web")
    op.drop_column("dossiers", "tva_jour_echeance")
    op.drop_column("dossiers", "tva_periodicite")
