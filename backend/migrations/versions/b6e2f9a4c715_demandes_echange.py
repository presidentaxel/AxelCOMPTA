"""demandes d'échange de la page publique

Revision ID: b6e2f9a4c715
Revises: d4b7e9a2c361

AXE-949. Une personne sans compte demande un échange depuis la landing.
La table n'a ni `tenant_id` ni `dossier_id` : la demande précède tout
portefeuille, il n'y a donc pas d'isolation par ligne à faire.

La RLS est pourtant **activée explicitement** : Supabase l'active seul sur
toute nouvelle table de `public` (déclencheur `ensure_rls`), et sans
politique le rôle web n'écrirait plus rien (« new row violates row-level
security policy »). Trois politiques, une par droit, laissent passer toutes
les lignes ; ce sont les droits par colonne qui limitent le rôle web.

Le rôle web (l'API) reçoit le strict nécessaire, colonne par colonne :
ajouter une ligne, lire de quoi dédoublonner et plafonner (e-mail et date),
noter le résultat de la notification. Les noms, organisations et messages
ne sont lus que par le rôle propriétaire (il contourne la RLS), celui des
tâches planifiées.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6e2f9a4c715"
down_revision: str | Sequence[str] | None = "d4b7e9a2c361"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demandes_echange",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("organisation", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notifiee_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tentatives", sa.Integer(), server_default="0", nullable=False),
        sa.Column("derniere_erreur", sa.String(), nullable=True),
        sa.CheckConstraint("role IN ('cabinet', 'centrale')", name="ck_demandes_echange_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_demandes_echange_email_cree_le", "demandes_echange", ["email", "cree_le"], unique=False
    )
    op.execute("ALTER TABLE demandes_echange ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY demandes_echange_ajout ON demandes_echange "
        "FOR INSERT TO axelcompta_web WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY demandes_echange_decompte ON demandes_echange "
        "FOR SELECT TO axelcompta_web USING (true)"
    )
    op.execute(
        "CREATE POLICY demandes_echange_notification ON demandes_echange "
        "FOR UPDATE TO axelcompta_web USING (true) WITH CHECK (true)"
    )
    op.execute("GRANT INSERT ON demandes_echange TO axelcompta_web")
    op.execute(
        "GRANT SELECT (id, email, cree_le, notifiee_le, tentatives) "
        "ON demandes_echange TO axelcompta_web"
    )
    op.execute(
        "GRANT UPDATE (notifiee_le, tentatives, derniere_erreur) "
        "ON demandes_echange TO axelcompta_web"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON demandes_echange FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS demandes_echange_notification ON demandes_echange")
    op.execute("DROP POLICY IF EXISTS demandes_echange_decompte ON demandes_echange")
    op.execute("DROP POLICY IF EXISTS demandes_echange_ajout ON demandes_echange")
    op.drop_index("ix_demandes_echange_email_cree_le", table_name="demandes_echange")
    op.drop_table("demandes_echange")
