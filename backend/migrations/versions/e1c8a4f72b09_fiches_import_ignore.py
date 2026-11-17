"""fiches d'import : statut ignoré

Revision ID: e1c8a4f72b09
Revises: d4b7e9a2c361

Une fiche ignorée sort de Toutes et d'Entreprises. Elle reste listée dans
la catégorie Ignoré, et peut revenir dans le calcul du statut.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1c8a4f72b09"
down_revision: str | Sequence[str] | None = "d4b7e9a2c361"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUTS = "statut IN ('a_importer', 'en_traitement', 'traitee', 'ignore')"
_AVANT = "statut IN ('a_importer', 'en_traitement', 'traitee')"


def upgrade() -> None:
    op.drop_constraint("fiches_import_statut", "fiches_import", type_="check")
    op.create_check_constraint("fiches_import_statut", "fiches_import", _STATUTS)


def downgrade() -> None:
    op.drop_constraint("fiches_import_statut", "fiches_import", type_="check")
    op.create_check_constraint("fiches_import_statut", "fiches_import", _AVANT)
