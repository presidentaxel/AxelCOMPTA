"""expert-comptable : habilitation, engagement, décisions

Revision ID: c9f3a1e6d248
Revises: a7d3e5c1b904

AXE-800. L'expert-comptable prend la charge juridique de ses changements :
- `habilitations_expert` : déclaration par un admin (nom, cabinet, Ordre,
  lettre de mission, dossiers couverts) ;
- `engagements_expert` : texte d'engagement accepté, mot pour mot, avec la
  date et l'adresse ;
- `decisions_expert` : chaque imputation, annulation ou qualification, avec
  l'auteur, le motif, la version de l'engagement et les écritures écrites
  avec elle (I6).
Les trois en ajout seul (trigger) ; RLS par portefeuille, ou par dossier.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f3a1e6d248"
down_revision: str | Sequence[str] | None = "a7d3e5c1b904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAR_PORTEFEUILLE = "tenant_id = current_setting('app.tenant_id', true)"
_PAR_DOSSIER = "axelcompta_dossier_visible(dossier_id)"


def _verrouiller(table: str, regle: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_isolation ON {table}
          FOR ALL TO axelcompta_web USING ({regle}) WITH CHECK ({regle})
        """
    )
    op.execute(f"GRANT SELECT, INSERT ON {table} TO axelcompta_web")
    op.execute(
        f"""
        CREATE TRIGGER {table}_immuable BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION axelcompta_interdire_mutation()
        """
    )


def upgrade() -> None:
    op.create_table(
        "habilitations_expert",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("cabinet", sa.String(), nullable=False),
        sa.Column("numero_ordre", sa.String(), nullable=False),
        sa.Column("lettre_mission", sa.String(), nullable=False),
        sa.Column("date_lettre", sa.Date(), nullable=False),
        sa.Column("dossiers", sa.JSON(), nullable=False),
        sa.Column("accordee_par", sa.String(), nullable=False),
        sa.Column("accordee_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        op.f("ix_habilitations_expert_tenant_id"), "habilitations_expert", ["tenant_id"]
    )
    op.create_table(
        "engagements_expert",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("texte", sa.String(), nullable=False),
        sa.Column("adresse", sa.String(), nullable=False),
        sa.Column("acteur", sa.String(), nullable=False),
        sa.Column("accepte_le", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_engagements_expert_tenant_id"), "engagements_expert", ["tenant_id"])
    op.create_table(
        "decisions_expert",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("ecriture_id", sa.String(), nullable=True),
        sa.Column("nature", sa.String(), nullable=False),
        sa.Column("motif", sa.String(), nullable=False),
        sa.Column("auteur", sa.String(), nullable=False),
        sa.Column("auteur_nom", sa.String(), nullable=False),
        sa.Column("version_engagement", sa.String(), nullable=False),
        sa.Column("decide_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ecritures", sa.JSON(), nullable=False),
    )
    op.create_index(op.f("ix_decisions_expert_dossier_id"), "decisions_expert", ["dossier_id"])
    _verrouiller("habilitations_expert", _PAR_PORTEFEUILLE)
    _verrouiller("engagements_expert", _PAR_PORTEFEUILLE)
    _verrouiller("decisions_expert", _PAR_DOSSIER)


def downgrade() -> None:
    for table in ("decisions_expert", "engagements_expert", "habilitations_expert"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immuable ON {table}")
        op.execute(f"REVOKE ALL ON {table} FROM axelcompta_web")
        op.execute(f"DROP POLICY IF EXISTS {table}_isolation ON {table}")
        op.drop_table(table)
