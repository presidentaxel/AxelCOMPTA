"""webhooks Rollee reçus

Revision ID: d6b2f8a4c3e7
Revises: c4e9a7d2b5f1
Create Date: 2026-11-11

AXE-820.
- `evenements_rollee` : chaque webhook reçu, gardé tel quel (identifiant =
  empreinte du corps, un webhook rejoué n'est gardé qu'une fois), puis
  traité par la file de jobs. Policy par portefeuille.
- `axelcompta_webhook_rollee(b_id)` : la route publique du webhook n'a pas
  d'identité ; cette fonction `SECURITY DEFINER` ne rend, pour un
  branchement Rollee actif, que son portefeuille et ses paramètres chiffrés
  (le secret de signature se déchiffre côté API, la clé n'est pas en base).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6b2f8a4c3e7"
down_revision: str | Sequence[str] | None = "c4e9a7d2b5f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"


def upgrade() -> None:
    op.create_table(
        "evenements_rollee",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("branchement_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("recu_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("traite_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resultat", sa.String(), nullable=True),
    )
    op.create_index(op.f("ix_evenements_rollee_tenant_id"), "evenements_rollee", ["tenant_id"])
    op.execute("ALTER TABLE evenements_rollee ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY evenements_rollee_isolation ON evenements_rollee FOR ALL "
        f"TO axelcompta_web USING ({_PORTEFEUILLE}) WITH CHECK ({_PORTEFEUILLE})"
    )
    op.execute("GRANT SELECT, INSERT ON evenements_rollee TO axelcompta_web")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION axelcompta_webhook_rollee(b_id varchar)
        RETURNS TABLE (tenant_id varchar, parametres_chiffres varchar)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
          SELECT b.tenant_id, b.parametres_chiffres FROM branchements b
           WHERE b.id = b_id AND b.type = 'rollee' AND b.actif
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION axelcompta_webhook_rollee(varchar) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION axelcompta_webhook_rollee(varchar) TO axelcompta_web")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS axelcompta_webhook_rollee(varchar)")
    op.execute("REVOKE ALL ON evenements_rollee FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS evenements_rollee_isolation ON evenements_rollee")
    op.drop_table("evenements_rollee")
