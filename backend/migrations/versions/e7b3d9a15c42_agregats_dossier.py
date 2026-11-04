"""agrégats du portefeuille, gardés en base (AXE-566)

Revision ID: e7b3d9a15c42
Revises: b6d1e9a43c20

La page Entreprises reconstruisait chaque dossier (grand livre, décisions,
liasse) à chaque ouverture, avec un cache de dix minutes en mémoire. Cette
table garde, par dossier, les valeurs qui coûtent : les montants de la
liasse, l'exercice et l'alerte de franchise de TVA.

Une ligne est périmée dès qu'une donnée dont elle dépend change. Ce ne sont
pas les routes qui s'en chargent, ce sont des triggers : une écriture posée
par la synchro Digifactory, un script ou une route périme la ligne de la
même façon, dans la même transaction que l'écriture. `version` monte à
chaque invalidation ; qui recalcule ne remplace la ligne que si `version`
n'a pas bougé depuis sa lecture, donc un calcul lent ne remet jamais en
base un résultat déjà périmé.

Lignes à périmer : une écriture (`ecritures`, insert seul, elle est
immuable), une décision humaine, une provision de clôture, et le dossier
lui-même (exercice, régime, forme juridique). Le statut d'invitation, les
preuves de l'exercice et la date du jour ne sont pas stockés : ils changent
sans écriture chez nous, et l'étape de frise se recalcule à la lecture.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b3d9a15c42"
down_revision: str | Sequence[str] | None = "b6d1e9a43c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, colonne qui porte l'id du dossier, événements)
_SOURCES = (
    ("ecritures", "dossier_id", "INSERT"),
    ("decisions_humaines", "dossier_id", "INSERT OR DELETE"),
    ("provisions_cloture", "dossier_id", "INSERT OR DELETE"),
)


def upgrade() -> None:
    op.create_table(
        "agregats_dossier",
        sa.Column(
            "dossier_id",
            sa.String(),
            sa.ForeignKey("dossiers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("a_jour", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version_calcul", sa.Integer(), nullable=True),
        sa.Column("ca_ht_cts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("charges_cts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("resultat_cts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("exercice_debut", sa.Date(), nullable=True),
        sa.Column("exercice_fin", sa.Date(), nullable=True),
        sa.Column("alerte_tva", sa.Text(), nullable=True),
        sa.Column("calcule_le", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agregats_dossier_tenant_id", "agregats_dossier", ["tenant_id"])
    op.execute("ALTER TABLE agregats_dossier ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY agregats_dossier_isolation ON agregats_dossier
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (
            axelcompta_dossier_visible(dossier_id)
            AND tenant_id = (SELECT d.tenant_id FROM dossiers d WHERE d.id = agregats_dossier.dossier_id)
          )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE ON agregats_dossier TO axelcompta_web")
    # SECURITY DEFINER : le trigger doit pouvoir périmer la ligne quel que
    # soit l'auteur de l'écriture, y compris un chauffeur (dont le contexte
    # RLS n'a pas de tenant) ou un script. `search_path` figé, comme il se
    # doit pour une fonction qui s'exécute avec les droits de son propriétaire.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION axelcompta_invalider_agregat()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
          cible text;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            cible := to_jsonb(OLD) ->> TG_ARGV[0];
          ELSE
            cible := to_jsonb(NEW) ->> TG_ARGV[0];
          END IF;
          UPDATE agregats_dossier
             SET a_jour = false, version = version + 1
           WHERE dossier_id = cible;
          IF NOT FOUND THEN
            INSERT INTO agregats_dossier (dossier_id, tenant_id, version, a_jour)
            SELECT id, tenant_id, 1, false FROM dossiers WHERE id = cible
            ON CONFLICT (dossier_id)
              DO UPDATE SET a_jour = false, version = agregats_dossier.version + 1;
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    for table, colonne, evenements in _SOURCES:
        op.execute(
            f"""
            CREATE TRIGGER {table}_perime_agregat
            AFTER {evenements} ON {table}
            FOR EACH ROW EXECUTE FUNCTION axelcompta_invalider_agregat('{colonne}')
            """
        )
    # Le dossier : seulement si une valeur a changé (un UPDATE sans effet ne
    # doit pas faire recalculer le portefeuille).
    op.execute(
        """
        CREATE TRIGGER dossiers_perime_agregat
        AFTER UPDATE ON dossiers
        FOR EACH ROW WHEN (to_jsonb(OLD) IS DISTINCT FROM to_jsonb(NEW))
        EXECUTE FUNCTION axelcompta_invalider_agregat('id')
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS dossiers_perime_agregat ON dossiers")
    for table, _colonne, _evenements in reversed(_SOURCES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_perime_agregat ON {table}")
    op.execute("DROP FUNCTION IF EXISTS axelcompta_invalider_agregat()")
    op.execute("REVOKE ALL ON agregats_dossier FROM axelcompta_web")
    op.execute("DROP POLICY IF EXISTS agregats_dossier_isolation ON agregats_dossier")
    op.drop_index("ix_agregats_dossier_tenant_id", table_name="agregats_dossier")
    op.drop_table("agregats_dossier")
