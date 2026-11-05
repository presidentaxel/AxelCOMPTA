"""Invariant I4 : aucune écriture datée dans un exercice clos

Revision ID: f1a6c3e9d257
Revises: e5b9d3f72a48

Doc 06 §1. Le domaine refuse déjà (`ledger.periodes`) ; le trigger tient
l'invariant pour tout écrivain, connexion propriétaire comprise. SECURITY
DEFINER : la lecture de `exercices_clos` ne dépend pas de la RLS de
l'appelant.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a6c3e9d257"
down_revision: str | Sequence[str] | None = "e5b9d3f72a48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION axelcompta_refuser_periode_close() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE
          close exercices_clos%ROWTYPE;
        BEGIN
          SELECT * INTO close FROM exercices_clos
           WHERE dossier_id = NEW.dossier_id AND NEW.date BETWEEN debut AND fin
           LIMIT 1;
          IF FOUND THEN
            RAISE EXCEPTION
              'I4 : exercice du % au % clos, écriture % datée du % refusée',
              close.debut, close.fin, NEW.id, NEW.date
              USING ERRCODE = 'check_violation';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER ecritures_hors_periode_close
        BEFORE INSERT ON ecritures
        FOR EACH ROW EXECUTE FUNCTION axelcompta_refuser_periode_close()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ecritures_hors_periode_close ON ecritures")
    op.execute("DROP FUNCTION IF EXISTS axelcompta_refuser_periode_close()")
