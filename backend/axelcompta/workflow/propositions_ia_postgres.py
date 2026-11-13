"""`PropositionsIa` sur Postgres (table `propositions_ia`, AXE-888)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId

from .propositions_ia import PropositionIa


class PostgresPropositionsIa:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def lister(self, dossier_id: DossierId, version: str) -> dict[str, PropositionIa]:
        with self._engine.connect() as connexion:
            lignes = connexion.execute(
                text(
                    "SELECT cle, categorie, confiance, justification, modele, cree_le "
                    "FROM propositions_ia WHERE dossier_id = :dossier AND version = :version"
                ),
                {"dossier": dossier_id, "version": version},
            ).all()
        return {
            ligne.cle: PropositionIa(
                dossier_id,
                ligne.cle,
                version,
                ligne.categorie,
                float(ligne.confiance),
                ligne.justification,
                ligne.modele,
                ligne.cree_le,
            )
            for ligne in lignes
        }

    def enregistrer(self, propositions: Sequence[PropositionIa]) -> None:
        if not propositions:
            return
        with self._engine.begin() as connexion:
            connexion.execute(
                text(
                    "INSERT INTO propositions_ia (dossier_id, cle, version, categorie, confiance, "
                    "justification, modele, cree_le) VALUES (:dossier_id, :cle, :version, "
                    ":categorie, :confiance, :justification, :modele, :cree_le) "
                    "ON CONFLICT (dossier_id, cle, version) DO NOTHING"
                ),
                [
                    {
                        "dossier_id": p.dossier_id,
                        "cle": p.cle,
                        "version": p.version,
                        "categorie": p.categorie,
                        "confiance": p.confiance,
                        "justification": p.justification,
                        "modele": p.modele,
                        "cree_le": p.cree_le,
                    }
                    for p in propositions
                ],
            )
