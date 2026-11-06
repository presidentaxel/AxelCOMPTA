"""index de lecture par dossier

Revision ID: c6e2a9f4b731
Revises: b3d8f1a6c924

AXE-824. Aucune table du grand livre n'avait d'index sur sa clé de lecture :
chaque grand livre parcourait toutes les lignes de toute la base (file
expert : 11,5 s à 200 dossiers). Mesures dans la PR.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c6e2a9f4b731"
down_revision: str | Sequence[str] | None = "b3d8f1a6c924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (nom, table, colonnes)
INDEX = (
    ("ix_ecritures_dossier_date", "ecritures", ["dossier_id", "date", "id"]),
    ("ix_lignes_ecriture_ecriture_id", "lignes_ecriture", ["ecriture_id"]),
    ("ix_propositions_categorisation_dossier_id", "propositions_categorisation", ["dossier_id"]),
    ("ix_decisions_humaines_dossier_id", "decisions_humaines", ["dossier_id"]),
)


def upgrade() -> None:
    for nom, table, colonnes in INDEX:
        op.create_index(nom, table, colonnes)


def downgrade() -> None:
    for nom, table, _colonnes in reversed(INDEX):
        op.drop_index(nom, table_name=table)
