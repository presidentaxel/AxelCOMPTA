"""numérotation continue des écritures par exercice (I3)

Revision ID: a3e8c1f5b297
Revises: e9c2a7f14b63

AXE-807, décision du 6 nov. : **une séquence par dossier et par exercice,
tous journaux confondus, dans l'ordre de validation**. Le numéro est
attribué par un trigger dans la transaction qui insère l'écriture : un
rollback rend le numéro, il n'y a pas de trou (pas de séquence Postgres).
`valide_le` est l'horodatage pris après le verrou du compteur : il croît
avec le numéro, c'est la `ValidDate` du FEC.

Reprise : les écritures existantes sont numérotées dans l'ordre exact du
FEC d'avant (date, à-nouveaux d'abord, identifiant), `valide_le` = leur
date. Un FEC déjà remis se régénère donc à l'identique.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e8c1f5b297"
down_revision: str | Sequence[str] | None = "e9c2a7f14b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Début de l'exercice qui contient `jour` pour le dossier : un exercice clos
# qui le couvre, sinon l'exercice en cours, sinon l'exercice suivant (une
# opération de février arrivée avant la clôture de l'année précédente).
_EXERCICE_DE = """
CREATE OR REPLACE FUNCTION axelcompta_exercice_de(d_id varchar, jour date)
RETURNS date LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT COALESCE(
    (SELECT c.debut FROM exercices_clos c
      WHERE c.dossier_id = d_id AND jour BETWEEN c.debut AND c.fin
      ORDER BY c.debut DESC LIMIT 1),
    (SELECT CASE WHEN jour > f.fin THEN f.fin + 1 ELSE f.debut END
       FROM (SELECT d.exercice_debut AS debut,
                    COALESCE(d.exercice_fin,
                      CASE WHEN to_char(d.exercice_debut, 'MM-DD') = '02-29'
                           THEN make_date(extract(year FROM d.exercice_debut)::int + 1, 2, 28)
                           ELSE (d.exercice_debut + interval '1 year')::date - 1 END) AS fin
               FROM dossiers d WHERE d.id = d_id) f)
  )
$$
"""

_NUMEROTER = """
CREATE OR REPLACE FUNCTION axelcompta_numeroter_ecriture() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  exercice date := axelcompta_exercice_de(NEW.dossier_id, NEW.date);
BEGIN
  INSERT INTO compteurs_ecritures (dossier_id, exercice_debut, dernier)
  VALUES (NEW.dossier_id, exercice, 1)
  ON CONFLICT (dossier_id, exercice_debut)
    DO UPDATE SET dernier = compteurs_ecritures.dernier + 1
  RETURNING dernier INTO NEW.numero;
  NEW.exercice_debut := exercice;
  NEW.valide_le := clock_timestamp();
  RETURN NEW;
END;
$$
"""

_REPRISE = """
WITH ordre AS (
  SELECT e.id,
         axelcompta_exercice_de(e.dossier_id, e.date) AS exercice,
         e.dossier_id
    FROM ecritures e
), numeros AS (
  SELECT o.id, o.exercice,
         row_number() OVER (
           PARTITION BY o.dossier_id, o.exercice
           ORDER BY e.date, (e.journal <> 'AN'), e.id
         ) AS numero
    FROM ordre o JOIN ecritures e ON e.id = o.id
)
UPDATE ecritures e
   SET numero = n.numero, exercice_debut = n.exercice, valide_le = e.date::timestamptz
  FROM numeros n
 WHERE n.id = e.id
"""


def upgrade() -> None:
    op.add_column("ecritures", sa.Column("numero", sa.BigInteger(), nullable=True))
    op.add_column("ecritures", sa.Column("exercice_debut", sa.Date(), nullable=True))
    op.add_column("ecritures", sa.Column("valide_le", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "compteurs_ecritures",
        sa.Column("dossier_id", sa.String(), sa.ForeignKey("dossiers.id"), nullable=False),
        sa.Column("exercice_debut", sa.Date(), nullable=False),
        sa.Column("dernier", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("dossier_id", "exercice_debut"),
    )
    # Écrit seulement par le trigger (SECURITY DEFINER) : aucun droit au rôle web.
    op.execute("ALTER TABLE compteurs_ecritures ENABLE ROW LEVEL SECURITY")
    op.execute(_EXERCICE_DE)
    op.execute("ALTER TABLE ecritures DISABLE TRIGGER ecritures_immuables")
    op.execute(_REPRISE)
    op.execute("ALTER TABLE ecritures ENABLE TRIGGER ecritures_immuables")
    op.execute(
        """
        INSERT INTO compteurs_ecritures (dossier_id, exercice_debut, dernier)
        SELECT dossier_id, exercice_debut, max(numero) FROM ecritures
         GROUP BY dossier_id, exercice_debut
        """
    )
    op.alter_column("ecritures", "numero", nullable=False)
    op.alter_column("ecritures", "exercice_debut", nullable=False)
    op.alter_column("ecritures", "valide_le", nullable=False)
    op.create_unique_constraint(
        "ecritures_numero_unique", "ecritures", ["dossier_id", "exercice_debut", "numero"]
    )
    op.execute(_NUMEROTER)
    op.execute(
        """
        CREATE TRIGGER ecritures_numerotation
        BEFORE INSERT ON ecritures
        FOR EACH ROW EXECUTE FUNCTION axelcompta_numeroter_ecriture()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ecritures_numerotation ON ecritures")
    op.execute("DROP FUNCTION IF EXISTS axelcompta_numeroter_ecriture()")
    op.drop_constraint("ecritures_numero_unique", "ecritures", type_="unique")
    op.execute("DROP FUNCTION IF EXISTS axelcompta_exercice_de(varchar, date)")
    op.drop_table("compteurs_ecritures")
    op.drop_column("ecritures", "valide_le")
    op.drop_column("ecritures", "exercice_debut")
    op.drop_column("ecritures", "numero")
