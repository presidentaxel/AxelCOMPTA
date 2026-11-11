"""le rôle web écrit l'identité et la confirmation du dossier

Revision ID: a3f8c2d71e46
Revises: e6b2d9f4a371

AXE-846. Le dirigeant saisit le siège, le capital et les associés de sa
société (`dossiers.identite`) : le rôle web reçoit l'UPDATE de cette seule
colonne, la policy `dossiers_isolation` limitant toujours la ligne à son
dossier.

Au passage, AXE-730 écrit `forme_juridique` et `a_confirmer` quand le
dirigeant confirme sa configuration, mais aucune migration ne donnait ce
droit au rôle web : la confirmation échouait en production (permission
refusée), et seuls les tests en mémoire passaient. On le donne ici.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3f8c2d71e46"
down_revision: str | Sequence[str] | None = "e6b2d9f4a371"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLONNES = "identite, forme_juridique, a_confirmer"


def upgrade() -> None:
    op.execute(f"GRANT UPDATE ({_COLONNES}) ON dossiers TO axelcompta_web")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({_COLONNES}) ON dossiers FROM axelcompta_web")
