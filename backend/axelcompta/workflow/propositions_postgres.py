"""Implémentation Postgres de PropositionRepository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, Row

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.rls import appliquer_rls

from .orm import propositions_categorisation as table
from .propositions import PropositionRepository


class PostgresPropositionRepository(PropositionRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enregistrer(self, ecriture_id: EcritureId, proposition: ProposedEntry) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                insert(table)
                .values(
                    ecriture_id=ecriture_id,
                    dossier_id=proposition.dossier_id,
                    categorie=proposition.categorie,
                    etage=proposition.etage.name,
                    confiance=proposition.confiance,
                )
                .on_conflict_do_nothing(index_elements=[table.c.ecriture_id])
            )

    def obtenir(self, dossier_id: DossierId, ecriture_id: EcritureId) -> ProposedEntry | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                select(table).where(
                    table.c.ecriture_id == ecriture_id, table.c.dossier_id == dossier_id
                )
            ).first()
        return None if ligne is None else _proposition(ligne)

    def lister(self, dossier_id: DossierId) -> dict[EcritureId, ProposedEntry]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(select(table).where(table.c.dossier_id == dossier_id)).all()
        return {EcritureId(ligne.ecriture_id): _proposition(ligne) for ligne in lignes}


def _proposition(ligne: Row[Any]) -> ProposedEntry:
    return ProposedEntry(
        dossier_id=DossierId(ligne.dossier_id),
        # L'identifiant de transaction d'origine n'est pas utilisé après
        # coup (seuls étage et confiance servent à la file de revue) :
        # on reprend l'id de l'écriture plutôt que de le persister.
        transaction_id=TransactionId(ligne.ecriture_id),
        categorie=ligne.categorie,
        etage=Etage[ligne.etage],
        confiance=ligne.confiance,
    )
