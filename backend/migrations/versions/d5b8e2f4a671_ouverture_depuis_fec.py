"""bilan d'ouverture repris d'un FEC, et déficits reportables du dossier

Revision ID: d5b8e2f4a671
Revises: c7e4a9d2f518

AXE-804. `ouvertures_importees` garde, pour chaque dossier, le FEC qui a
servi à son bilan d'ouverture : nom, empreinte, clôture, qui l'a importé
(dirigeant ou expert-comptable), son attestation, la correspondance des
comptes, les déficits déclarés (en euros) et l'écriture d'à-nouveaux. Une seule par
dossier : l'ouverture est verrouillée, une correction passe par une OD.
Ajout seul, RLS par dossier.

`dossiers.deficits_anterieurs_euros` : déficits reportables à l'ouverture de
l'exercice en cours (2033-D ligne 870 du précédent), en euros comme la
liasse. Le rôle web le pose à l'import et au passage d'exercice.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5b8e2f4a671"
down_revision: str | Sequence[str] | None = "c7e4a9d2f518"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dossiers",
        sa.Column("deficits_anterieurs_euros", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "ouvertures_importees",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False, unique=True
        ),
        sa.Column("nom_fichier", sa.String(), nullable=False),
        sa.Column("empreinte", sa.String(), nullable=False),
        sa.Column("cloture", sa.Date(), nullable=False),
        sa.Column("ouverture", sa.Date(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("par", sa.String(), nullable=False),
        sa.Column("auteur_nom", sa.String(), nullable=True),
        sa.Column("motif", sa.String(), nullable=True),
        sa.Column("attestation", sa.Text(), nullable=False),
        sa.Column("correspondance", sa.JSON(), nullable=False),
        sa.Column("deficits_euros", sa.BigInteger(), nullable=False),
        sa.Column("ecriture_id", sa.String(), nullable=False),
        sa.Column("le", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("ALTER TABLE ouvertures_importees ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY ouvertures_importees_isolation ON ouvertures_importees
          FOR ALL TO axelcompta_web
          USING (axelcompta_dossier_visible(dossier_id))
          WITH CHECK (axelcompta_dossier_visible(dossier_id))
        """
    )
    op.execute(
        """
        CREATE TRIGGER ouvertures_importees_immuables
        BEFORE UPDATE OR DELETE ON ouvertures_importees
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )
    op.execute("GRANT SELECT, INSERT ON ouvertures_importees TO axelcompta_web")
    op.execute("GRANT UPDATE (deficits_anterieurs_euros) ON dossiers TO axelcompta_web")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (deficits_anterieurs_euros) ON dossiers FROM axelcompta_web")
    op.execute(
        "DROP TRIGGER IF EXISTS ouvertures_importees_immuables ON ouvertures_importees"
    )
    op.execute("DROP POLICY IF EXISTS ouvertures_importees_isolation ON ouvertures_importees")
    op.execute("REVOKE ALL ON ouvertures_importees FROM axelcompta_web")
    op.drop_table("ouvertures_importees")
    op.drop_column("dossiers", "deficits_anterieurs_euros")
