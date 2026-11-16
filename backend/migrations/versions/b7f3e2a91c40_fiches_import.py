"""fiches d'import d'un chauffeur et leurs documents

Revision ID: b7f3e2a91c40
Revises: a4c8e1d73b29

AXE-941. Une fiche par chauffeur à reprendre, dans le portefeuille qui l'a
ouverte ; ses documents (liasse, FEC, Kbis…) gardés en base. Le rôle web
lit, crée et modifie les fiches ; il dépose et retire les documents.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f3e2a91c40"
down_revision: str | Sequence[str] | None = "a4c8e1d73b29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DU_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"


def upgrade() -> None:
    op.create_table(
        "fiches_import",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("prenom", sa.String(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("champs", sa.JSON(), nullable=False),
        sa.Column("registre", sa.JSON(), nullable=True),
        sa.Column("dossier_id", sa.String(), nullable=True),
        sa.Column("cree_par", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("maj_par", sa.String(), nullable=False),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "statut IN ('a_importer', 'en_traitement', 'traitee')", name="fiches_import_statut"
        ),
    )
    op.create_index("ix_fiches_import_tenant_id", "fiches_import", ["tenant_id"])
    op.create_table(
        "documents_import",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("fiche_id", sa.String(), sa.ForeignKey("fiches_import.id"), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("categorie", sa.String(), nullable=False),
        sa.Column("exercice", sa.Integer(), nullable=True),
        sa.Column("nom_fichier", sa.String(), nullable=False),
        sa.Column("type_mime", sa.String(), nullable=False),
        sa.Column("taille", sa.Integer(), nullable=False),
        sa.Column("empreinte", sa.String(), nullable=False),
        sa.Column("contenu", sa.LargeBinary(), nullable=False),
        sa.Column("depose_par", sa.String(), nullable=False),
        sa.Column("depose_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_import_fiche_id", "documents_import", ["fiche_id"])
    for table, droits in (
        ("fiches_import", "SELECT, INSERT, UPDATE"),
        ("documents_import", "SELECT, INSERT, DELETE"),
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
              FOR ALL TO axelcompta_web
              USING ({_DU_PORTEFEUILLE})
              WITH CHECK ({_DU_PORTEFEUILLE})
            """
        )
        op.execute(f"GRANT {droits} ON {table} TO axelcompta_web")


def downgrade() -> None:
    for table in ("documents_import", "fiches_import"):
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
    op.drop_index("ix_documents_import_fiche_id", table_name="documents_import")
    op.drop_table("documents_import")
    op.drop_index("ix_fiches_import_tenant_id", table_name="fiches_import")
    op.drop_table("fiches_import")
