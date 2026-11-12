"""Lecture des opérations suivies, toute la base (AXE-900).

Connexion propriétaire, comme le contrôle de balance des tâches planifiées :
l'indicateur est global, pas par dossier. Seules les propositions datées
(`cree_le`, depuis le 12/11/2026) sont lues.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .decisions import CATEGORIE_A_PRECISER, CATEGORIE_ANNULATION
from .indicateurs_categorisation import OperationSuivie
from .synchro import COMPTE_ATTENTE

_REQUETE = text(
    """
    SELECT p.etage, p.categorie, e.date, p.cree_le,
           EXISTS (SELECT 1 FROM lignes_ecriture l
                    WHERE l.ecriture_id = p.ecriture_id AND l.compte = :attente),
           (SELECT MIN(d.decide_le) FROM decisions_humaines d
             WHERE d.ecriture_id = p.ecriture_id
               AND d.categorie NOT IN (:annulation, :a_preciser))
      FROM propositions_categorisation p
      JOIN ecritures e ON e.id = p.ecriture_id
     WHERE p.cree_le >= :depuis
    """
)


def operations_suivies(engine: Engine, depuis: datetime) -> list[OperationSuivie]:
    parametres = {
        "attente": COMPTE_ATTENTE,
        "annulation": CATEGORIE_ANNULATION,
        "a_preciser": CATEGORIE_A_PRECISER,
        "depuis": depuis,
    }
    with engine.connect() as connexion:
        lignes = connexion.execute(_REQUETE, parametres).all()
    return [
        OperationSuivie(
            etage=etage,
            categorie=categorie,
            date_operation=jour,
            cree_le=cree_le,
            a_trancher=bool(a_trancher),
            decide_le=_utc(decide_le),
        )
        for etage, categorie, jour, cree_le, a_trancher, decide_le in lignes
    ]


def _utc(moment: datetime | None) -> datetime | None:
    """`decisions_humaines.decide_le` est sans fuseau : l'heure UTC."""
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=UTC)
