"""AXE-988 : un document reclassé est relu.

Revision ID: a3d9e6f1c204
Revises: f7a2c9e4b318
Create Date: 2026-11-18

Reclasser un document (à la main, ou en le redéposant dans une catégorie
plus précise) le relit selon sa nouvelle catégorie : un récapitulatif Uber
resté en « Autre » est lu. Le rôle web peut déjà changer la catégorie,
l'exercice, l'emplacement et la clé de stockage (f7a2c9e4b318) ; il peut
désormais écrire aussi ce que la relecture en tire. Le contenu, l'empreinte
et le dépôt (qui, quand) restent hors de sa portée.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a3d9e6f1c204"
down_revision: str | Sequence[str] | None = "f7a2c9e4b318"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RELECTURE = "statut_traitement, resume, donnees"


def upgrade() -> None:
    op.execute(f"GRANT UPDATE ({_RELECTURE}) ON documents_import TO axelcompta_web")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({_RELECTURE}) ON documents_import FROM axelcompta_web")
