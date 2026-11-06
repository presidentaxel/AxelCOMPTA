"""forme juridique à confirmer pour les SAS et SARL déjà créées

Revision ID: e4b9d2a7c815
Revises: e9c2a7f14b63

AXE-730. Sirene ne distingue pas SAS et SASU, ni SARL et EURL (AXE-834).
Les dossiers créés avant AXE-834 portent SAS ou SARL sans que personne ne
l'ait confirmé, et `a_confirmer` y est vide. On marque leur forme « à
confirmer » : le dirigeant tranche avant la clôture et la liasse.

Une SASU, une EURL ou une EI est déjà une forme certaine : pas touchée.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e4b9d2a7c815"
down_revision: str | Sequence[str] | None = "e9c2a7f14b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE dossiers
        SET a_confirmer = '["forme_juridique"]'::json
        WHERE forme_juridique IN ('SAS', 'SARL')
          AND a_confirmer::jsonb = '[]'::jsonb
        """
    )


def downgrade() -> None:
    # Sans retour : après la migration, on ne distingue plus une forme marquée
    # ici d'une forme marquée par Sirene. Laisser « à confirmer » est sans
    # risque (le dirigeant confirme une fois de plus).
    pass
