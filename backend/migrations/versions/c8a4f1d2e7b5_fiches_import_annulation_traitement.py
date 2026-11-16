"""fiches d'import : annulation, emplacement et traitement des documents

Revision ID: c8a4f1d2e7b5
Revises: b7f3e2a91c40

AXE-947. Un import annulé sort de la liste (rien ne s'efface). Chaque
document garde l'emplacement où il a été déposé et son statut de
traitement : lu automatiquement (FEC, QIF), à lire, ou illisible.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8a4f1d2e7b5"
down_revision: str | Sequence[str] | None = "b7f3e2a91c40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fiches_import", sa.Column("annulee_le", sa.DateTime(timezone=True), nullable=True))
    op.add_column("fiches_import", sa.Column("annulee_par", sa.String(), nullable=True))
    op.add_column(
        "documents_import",
        sa.Column("emplacement", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "documents_import",
        sa.Column("statut_traitement", sa.String(), nullable=False, server_default="a_traiter"),
    )
    op.add_column(
        "documents_import", sa.Column("resume", sa.String(), nullable=False, server_default="")
    )
    op.create_check_constraint(
        "documents_import_statut_traitement",
        "documents_import",
        "statut_traitement IN ('a_traiter', 'traite', 'illisible')",
    )


def downgrade() -> None:
    op.drop_constraint("documents_import_statut_traitement", "documents_import", type_="check")
    for colonne in ("resume", "statut_traitement", "emplacement"):
        op.drop_column("documents_import", colonne)
    op.drop_column("fiches_import", "annulee_par")
    op.drop_column("fiches_import", "annulee_le")
