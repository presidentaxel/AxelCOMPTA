"""une demande faite pendant un job en cours n'est plus perdue

Revision ID: b6e2d8f1c093
Revises: f3a9c7e15d82
Create Date: 2026-11-14

AXE-921. L'index `jobs_un_actif_par_type` (en attente ou en cours) absorbait
une demande faite pendant un job en cours, alors que ce job avait déjà lu ce
qu'il devait faire : SEVEN CAR PRESTIGE ajouté pendant une synchro n'a jamais
été créé. Désormais, seules les demandes **en attente et identiques** (même
portefeuille, type et payload) se fusionnent : une demande pendant un job en
cours attend son tour, et deux dossiers différents ont chacun leur job.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b6e2d8f1c093"
down_revision: str | Sequence[str] | None = "f3a9c7e15d82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobs_un_actif_par_type")
    op.execute(
        """
        CREATE UNIQUE INDEX jobs_une_demande_en_attente ON jobs (tenant_id, type, payload)
        WHERE statut = 'en_attente'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobs_une_demande_en_attente")
    # Avant de recréer l'ancien index, une seule demande active par type :
    # les demandes en attente en trop sont abandonnées.
    op.execute(
        """
        DELETE FROM jobs j USING jobs k
        WHERE j.statut = 'en_attente' AND k.statut IN ('en_attente', 'en_cours')
          AND j.tenant_id = k.tenant_id AND j.type = k.type AND j.cree_le > k.cree_le
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX jobs_un_actif_par_type ON jobs (tenant_id, type)
        WHERE statut IN ('en_attente', 'en_cours')
        """
    )
