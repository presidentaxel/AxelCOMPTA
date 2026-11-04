"""Le rôle web peut suspendre ou supprimer une règle de rappel.

Revision ID: b7e1c4a92f30
Revises: a1d4e8c72b09

La création avait SELECT et INSERT. Suspendre écrit `actif`, supprimer
retire la ligne et détache les rappels déjà enregistrés.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7e1c4a92f30"
down_revision: str | Sequence[str] | None = "a1d4e8c72b09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "GRANT UPDATE (message, canaux, portee, dossier_ids, declencheur, jours_avant, actif) "
        "ON regles_rappel TO axelcompta_web"
    )
    op.execute("GRANT DELETE ON regles_rappel TO axelcompta_web")
    op.execute("GRANT UPDATE (regle_id) ON rappels TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (regle_id) ON rappels FROM axelcompta_web")
    op.execute("REVOKE DELETE ON regles_rappel FROM axelcompta_web")
    op.execute(
        "REVOKE UPDATE (message, canaux, portee, dossier_ids, declencheur, jours_avant, actif) "
        "ON regles_rappel FROM axelcompta_web"
    )
