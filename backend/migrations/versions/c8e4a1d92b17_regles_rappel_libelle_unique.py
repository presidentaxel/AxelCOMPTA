"""Un libellé de règle de rappel, une fois par portefeuille.

Deux ouvertures de /rappels lisaient une liste vide et créaient chacune
les trois règles préfaites. La contrainte empêche le doublon ; les lignes
déjà en double sont rattachées à la plus ancienne puis retirées.

Revision ID: c8e4a1d92b17
Revises: e7b3d9a15c42
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8e4a1d92b17"
down_revision: str | Sequence[str] | None = "e7b3d9a15c42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE rappels AS r
        SET regle_id = garde.id
        FROM regles_rappel AS doublon
        JOIN (
            SELECT tenant_id, libelle, MIN(id) AS id
            FROM regles_rappel
            GROUP BY tenant_id, libelle
        ) AS garde
          ON garde.tenant_id = doublon.tenant_id
         AND garde.libelle = doublon.libelle
        WHERE r.regle_id = doublon.id
          AND doublon.id <> garde.id
        """
    )
    op.execute(
        """
        DELETE FROM regles_rappel AS doublon
        USING (
            SELECT tenant_id, libelle, MIN(id) AS id
            FROM regles_rappel
            GROUP BY tenant_id, libelle
        ) AS garde
        WHERE doublon.tenant_id = garde.tenant_id
          AND doublon.libelle = garde.libelle
          AND doublon.id <> garde.id
        """
    )
    op.create_unique_constraint(
        "uq_regles_rappel_tenant_libelle",
        "regles_rappel",
        ["tenant_id", "libelle"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_regles_rappel_tenant_libelle", "regles_rappel", type_="unique")
