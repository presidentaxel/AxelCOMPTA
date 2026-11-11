"""plusieurs intégrations de chaque type par portefeuille

Revision ID: b8d4e1f7a2c6
Revises: e6b2d9f4a371
Create Date: 2026-11-11

AXE-872.
- `branchements` : une intégration nommée (SMTP, SMS, Digifactory…),
  plusieurs par type, une seule par défaut (index unique partiel).
  Paramètres chiffrés, comme avant.
- `branchements_dossier` : le branchement qu'un dossier utilise pour un
  type, quand ce n'est pas celui par défaut.
- `envois_rappel.branchement_id` : par quel branchement l'envoi est parti.
- Reprise : chaque ligne de `integrations_envoi` devient le branchement par
  défaut de son canal (« E-mail », « SMS »), puis la table disparaît. Le
  `downgrade` refait l'inverse avec les branchements par défaut.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4e1f7a2c6"
down_revision: str | Sequence[str] | None = "e6b2d9f4a371"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"


def _rls(table: str, droits: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_isolation ON {table} FOR ALL TO axelcompta_web "
        f"USING ({_PORTEFEUILLE}) WITH CHECK ({_PORTEFEUILLE})"
    )
    op.execute(f"GRANT {droits} ON {table} TO axelcompta_web")


def _sans_rls(table: str) -> None:
    op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
    op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")


def upgrade() -> None:
    op.create_table(
        "branchements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("fournisseur", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("parametres_chiffres", sa.String(), nullable=False),
        sa.Column("par_defaut", sa.Boolean(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False),
        sa.Column("maj_par", sa.String(), nullable=False),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "type", "nom", name="uq_branchements_nom"),
    )
    op.create_index(
        "uq_branchements_defaut",
        "branchements",
        ["tenant_id", "type"],
        unique=True,
        postgresql_where=sa.text("par_defaut"),
    )
    op.create_table(
        "branchements_dossier",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), primary_key=True),
        sa.Column("type", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "branchement_id", sa.String(), sa.ForeignKey("branchements.id"), nullable=False
        ),
    )
    op.add_column("envois_rappel", sa.Column("branchement_id", sa.String(), nullable=True))
    op.execute(
        """
        INSERT INTO branchements (id, tenant_id, type, fournisseur, nom, parametres_chiffres,
                                  par_defaut, actif, maj_par, maj_le)
        SELECT gen_random_uuid()::text, tenant_id, canal, fournisseur,
               CASE canal WHEN 'mail' THEN 'E-mail' ELSE 'SMS' END,
               parametres_chiffres, true, true, maj_par, maj_le
          FROM integrations_envoi
        """
    )
    _sans_rls("integrations_envoi")
    op.drop_table("integrations_envoi")
    _rls("branchements", "SELECT, INSERT, UPDATE")
    _rls("branchements_dossier", "SELECT, INSERT, UPDATE, DELETE")


def downgrade() -> None:
    op.create_table(
        "integrations_envoi",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("canal", sa.String(), primary_key=True),
        sa.Column("fournisseur", sa.String(), nullable=False),
        sa.Column("parametres_chiffres", sa.String(), nullable=False),
        sa.Column("maj_par", sa.String(), nullable=False),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        """
        INSERT INTO integrations_envoi (tenant_id, canal, fournisseur, parametres_chiffres,
                                        maj_par, maj_le)
        SELECT tenant_id, type, fournisseur, parametres_chiffres, maj_par, maj_le
          FROM branchements
         WHERE type IN ('mail', 'sms') AND par_defaut AND actif
        """
    )
    _rls("integrations_envoi", "SELECT, INSERT, UPDATE")
    op.drop_column("envois_rappel", "branchement_id")
    for table in ("branchements_dossier", "branchements"):
        _sans_rls(table)
        op.drop_table(table)
