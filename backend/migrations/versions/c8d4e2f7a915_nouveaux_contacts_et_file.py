"""nouveaux contacts Digifactory proposés, et file de jobs suivie

Revision ID: c8d4e2f7a915
Revises: d1e8c4a73f29

AXE-845.
* `jobs` : résultat et fin pour l'écran, au plus une demande active par
  portefeuille et par type (index unique partiel), et le gestionnaire
  dépose et lit **les demandes de son portefeuille** (policy par tenant).
  Le worker (rôle propriétaire) reste le seul à les exécuter.
* `contacts_proposes` (réécrite par le worker) et `decisions_contacts`
  (append-only) : RLS par portefeuille.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4e2f7a915"
down_revision: str | Sequence[str] | None = "d1e8c4a73f29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DU_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"


def upgrade() -> None:
    op.add_column("jobs", sa.Column("resultat", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("termine_le", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        CREATE UNIQUE INDEX jobs_un_actif_par_type ON jobs (tenant_id, type)
        WHERE statut IN ('en_attente', 'en_cours')
        """
    )
    op.execute(
        f"""
        CREATE POLICY jobs_du_portefeuille ON jobs FOR ALL TO axelcompta_web
          USING ({_DU_PORTEFEUILLE}) WITH CHECK ({_DU_PORTEFEUILLE})
        """
    )
    op.execute("GRANT SELECT, INSERT ON jobs TO axelcompta_web")
    op.create_table(
        "contacts_proposes",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_nr", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("siren", sa.String(), nullable=True),
        sa.Column("forme", sa.String(), nullable=True),
        sa.Column("exercice_debut", sa.Date(), nullable=True),
        sa.Column("code_naf", sa.String(), nullable=True),
        sa.Column("avertissements", sa.JSON(), nullable=False),
        sa.Column("cessee", sa.Boolean(), nullable=False),
        sa.Column("detecte_le", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "contact_nr"),
    )
    op.create_table(
        "decisions_contacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rang", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_nr", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('ajouter', 'ignorer', 'reprendre')", name="decisions_contacts_valeur"
        ),
    )
    op.create_index("ix_decisions_contacts_tenant_id", "decisions_contacts", ["tenant_id"])
    for table in ("contacts_proposes", "decisions_contacts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table} FOR ALL TO axelcompta_web
              USING ({_DU_PORTEFEUILLE}) WITH CHECK ({_DU_PORTEFEUILLE})
            """
        )
    op.execute("GRANT SELECT ON contacts_proposes TO axelcompta_web")
    op.execute("GRANT SELECT, INSERT ON decisions_contacts TO axelcompta_web")
    op.execute(
        """
        CREATE TRIGGER decisions_contacts_immuables
        BEFORE UPDATE OR DELETE ON decisions_contacts
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS decisions_contacts_immuables ON decisions_contacts")
    for table in ("decisions_contacts", "contacts_proposes"):
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
    op.drop_index("ix_decisions_contacts_tenant_id", table_name="decisions_contacts")
    op.drop_table("decisions_contacts")
    op.drop_table("contacts_proposes")
    op.execute("REVOKE ALL ON jobs FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS jobs_du_portefeuille ON jobs")
    op.execute("DROP INDEX IF EXISTS jobs_un_actif_par_type")
    op.drop_column("jobs", "termine_le")
    op.drop_column("jobs", "resultat")
