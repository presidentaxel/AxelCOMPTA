"""comptes à choisir : ce que le gestionnaire en voit

Revision ID: a7d3e5c1b904
Revises: b8e4c2d7a613

AXE-851. Un compte « à décider » (AXE-729) fait écarter ses opérations par
la synchro, sans écriture ni question. Le gestionnaire doit le voir, mais
seulement en nombres (doc 19 §2.4) : comptes en attente, depuis quand, et
combien d'opérations attendent.

Ces opérations ne sont que dans l'archive brute (`ingestion_brut`), que le
rôle web ne lit pas : elle porte les libellés et les IBAN. Plutôt que de lui
ouvrir l'archive, une fonction `SECURITY DEFINER` ne renvoie que des
comptages. Elle applique elle-même la règle de `dossiers_isolation` (le
dossier du jeton, ou les dossiers de son portefeuille) : sous `SECURITY
DEFINER`, les policies ne s'appliquent plus.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7d3e5c1b904"
down_revision: str | Sequence[str] | None = "b8e4c2d7a613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION axelcompta_comptes_a_choisir(ids varchar[])
        RETURNS TABLE (dossier_id varchar, nombre bigint, depuis timestamptz, operations bigint)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
          WITH visibles AS (
            SELECT d.id FROM dossiers d
            WHERE d.id = ANY(ids)
              AND (d.id = current_setting('app.dossier_id', true)
                   OR d.tenant_id = current_setting('app.tenant_id', true))
          ),
          en_attente AS (
            SELECT c.dossier_id, c.identifiant, c.cree_le
            FROM comptes_bancaires c JOIN visibles v ON v.id = c.dossier_id
            WHERE c.retenu IS NULL
          )
          SELECT e.dossier_id::varchar,
                 count(DISTINCT e.identifiant),
                 min(e.cree_le),
                 (SELECT count(DISTINCT b.transaction_id)
                    FROM ingestion_brut b
                    JOIN en_attente a
                      ON a.dossier_id = b.dossier_id
                     AND a.identifiant = btrim(b.payload->>'account_id')
                   WHERE b.dossier_id = e.dossier_id)
          FROM en_attente e
          GROUP BY e.dossier_id
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION axelcompta_comptes_a_choisir(varchar[]) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION axelcompta_comptes_a_choisir(varchar[]) TO axelcompta_web"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS axelcompta_comptes_a_choisir(varchar[])")
