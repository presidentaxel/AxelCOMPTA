"""documents d'import : archives, contenu dans le bucket, données lues

Revision ID: f7a2c9e4b318
Revises: e1c8a4f72b09

AXE-970. Un document d'import peut sortir d'une archive zip (`origine_id`,
supprimé avec elle), vivre dans le bucket S3 privé (`cle_stockage`, le
contenu en base devient facultatif) et garder ce qui en a été lu
(`donnees` : un FEC, ses soldes par compte). Le rôle web peut reclasser un
document (catégorie, exercice, emplacement, clé).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a2c9e4b318"
down_revision: str | Sequence[str] | None = "e1c8a4f72b09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RECLASSEMENT = "categorie, exercice, emplacement, cle_stockage"


def upgrade() -> None:
    op.alter_column("documents_import", "contenu", existing_type=sa.LargeBinary(), nullable=True)
    op.add_column("documents_import", sa.Column("origine_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "documents_import_origine_id_fkey",
        "documents_import",
        "documents_import",
        ["origine_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_documents_import_origine_id", "documents_import", ["origine_id"])
    op.add_column(
        "documents_import",
        sa.Column("cle_stockage", sa.String(), nullable=False, server_default=""),
    )
    op.add_column("documents_import", sa.Column("donnees", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "documents_import_contenu_quelque_part",
        "documents_import",
        "contenu IS NOT NULL OR cle_stockage <> ''",
    )
    op.execute(f"GRANT UPDATE ({_RECLASSEMENT}) ON documents_import TO axelcompta_web")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({_RECLASSEMENT}) ON documents_import FROM axelcompta_web")
    op.drop_constraint("documents_import_contenu_quelque_part", "documents_import", type_="check")
    op.drop_column("documents_import", "donnees")
    op.drop_column("documents_import", "cle_stockage")
    op.drop_index("ix_documents_import_origine_id", table_name="documents_import")
    op.drop_constraint("documents_import_origine_id_fkey", "documents_import", type_="foreignkey")
    op.drop_column("documents_import", "origine_id")
    # Un contenu parti dans le bucket ne revient pas : la descente suppose
    # qu'il n'y en a pas (sinon, les rapatrier d'abord).
    op.alter_column("documents_import", "contenu", existing_type=sa.LargeBinary(), nullable=False)
