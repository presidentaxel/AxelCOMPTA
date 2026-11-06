"""moyen de paiement gardé avec la proposition d'origine

Revision ID: d1e7a3c9f264
Revises: c8d4e2f7a915

AXE-836 : comment l'argent est sorti (carte, virement, prélèvement,
retrait), lu dans `operation_type` de Digifactory. Jusqu'ici il ne vivait que
dans l'archive brute, que l'API ne lit pas. Reprise : la dernière version
archivée de chaque opération (« unknown » ne dit rien : NULL).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e7a3c9f264"
down_revision: str | Sequence[str] | None = "c8d4e2f7a915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "propositions_categorisation", sa.Column("moyen_paiement", sa.String(), nullable=True)
    )
    op.execute(
        """
        UPDATE propositions_categorisation p
           SET moyen_paiement = NULLIF(lower(trim(dernier.type_operation)), 'unknown')
          FROM (
            SELECT DISTINCT ON (b.dossier_id, b.source, b.transaction_id)
                   b.dossier_id || ':' || b.source || '-' || b.transaction_id AS ecriture_id,
                   b.payload::jsonb ->> 'operation_type' AS type_operation
              FROM ingestion_brut b
             WHERE b.transaction_id IS NOT NULL
             ORDER BY b.dossier_id, b.source, b.transaction_id, b.recu_le DESC
          ) dernier
         WHERE dernier.ecriture_id = p.ecriture_id
           AND NULLIF(trim(dernier.type_operation), '') IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("propositions_categorisation", "moyen_paiement")
