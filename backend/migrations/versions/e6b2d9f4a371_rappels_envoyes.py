"""rappels envoyés par l'e-mail et le SMS du gestionnaire

Revision ID: e6b2d9f4a371
Revises: d4a8f2c6e195

AXE-808.
- `integrations_envoi` : SMTP ou fournisseur de SMS du portefeuille,
  paramètres chiffrés (Fernet, clé hors base). Le rôle web les écrit et les
  lit, chiffrés ; il ne les déchiffre jamais à l'écran.
- `envois_rappel` : un envoi par rappel et par canal, son statut et sa
  raison. Le rôle web les crée et les lit ; le worker (propriétaire) les met
  à jour.
- `desinscriptions` : le chauffeur arrête un canal par le lien du message.
  Le lien est public (pas de compte) : la fonction `SECURITY DEFINER`
  `axelcompta_desinscrire` n'écrit que cette ligne ; la signature du lien est
  vérifiée par l'API avant l'appel.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6b2d9f4a371"
down_revision: str | Sequence[str] | None = "d4a8f2c6e195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"


def _rls(table: str, regle: str, droits: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_isolation ON {table} FOR ALL TO axelcompta_web "
        f"USING ({regle}) WITH CHECK ({regle})"
    )
    op.execute(f"GRANT {droits} ON {table} TO axelcompta_web")


def upgrade() -> None:
    op.create_table(
        "integrations_envoi",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("canal", sa.String(), primary_key=True),
        sa.Column("fournisseur", sa.String(), nullable=False),
        sa.Column("parametres_chiffres", sa.String(), nullable=False),
        sa.Column("maj_par", sa.String(), nullable=False),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "envois_rappel",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rappel_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("canal", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("tentatives", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raison", sa.String(), nullable=True),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_envois_rappel_tenant_id"), "envois_rappel", ["tenant_id"])
    op.create_index(op.f("ix_envois_rappel_dossier_id"), "envois_rappel", ["dossier_id"])
    op.create_table(
        "desinscriptions",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), primary_key=True),
        sa.Column("canal", sa.String(), primary_key=True),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
    )
    _rls("integrations_envoi", _PORTEFEUILLE, "SELECT, INSERT, UPDATE")
    _rls("envois_rappel", _PORTEFEUILLE, "SELECT, INSERT")
    _rls("desinscriptions", "axelcompta_dossier_visible(dossier_id)", "SELECT")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION axelcompta_desinscrire(d_id varchar, c varchar)
        RETURNS void LANGUAGE sql VOLATILE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
          INSERT INTO desinscriptions (dossier_id, canal, le)
          SELECT d.id, c, now() FROM dossiers d WHERE d.id = d_id AND c IN ('mail', 'sms')
          ON CONFLICT DO NOTHING
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION axelcompta_desinscrire(varchar, varchar) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION axelcompta_desinscrire(varchar, varchar) TO axelcompta_web"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS axelcompta_desinscrire(varchar, varchar)")
    for table in ("desinscriptions", "envois_rappel", "integrations_envoi"):
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.drop_table(table)
