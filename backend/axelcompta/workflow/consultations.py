"""Journal des dossiers ouverts par le compte de test (AXE-822).

Chaque ouverture de l'espace chauffeur d'un dossier par ce compte laisse une
ligne au journal d'audit : qui, quel dossier, quand. Le compte lit tout un
portefeuille ; la trace dit ce qu'il a vraiment regardé.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls

from .audit import noter

ACTE_CONSULTATION_TEST = "consultation_compte_test"


class JournalConsultations(Protocol):
    def noter(self, dossier_id: DossierId, acteur: UserId, le: datetime) -> None: ...


class PostgresJournalConsultations:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def noter(self, dossier_id: DossierId, acteur: UserId, le: datetime) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            noter(connexion, dossier_id, ACTE_CONSULTATION_TEST, "compte de test", acteur, le)


@dataclass
class JournalConsultationsMemoire:
    lignes: list[tuple[DossierId, UserId, datetime]] = field(default_factory=list)

    def noter(self, dossier_id: DossierId, acteur: UserId, le: datetime) -> None:
        self.lignes.append((dossier_id, acteur, le))
