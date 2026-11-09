"""Une décision humaine et son écriture de reclassement, tout ou rien (AXE-852).

Depuis AXE-420, une décision écrit une OD `{S}:decision-k`. La décision et
l'OD partaient dans deux transactions : si la seconde échouait (coupure,
période close, déséquilibre), la décision restait sans son écriture, et
l'écran ne disait plus la même chose que le FEC.

Les reclassements se calculent d'abord, sans rien écrire
(`reclassement.reclasser`, pur). Puis `EcrireDecisions` écrit les décisions
et leurs OD ensemble :

* `PostgresDecisionsEtReclassements` : une seule transaction ;
* `EnSequence` : pour les dépôts en mémoire (tests, démo). Les écritures
  d'abord, qui portent les contrôles d'invariants : une OD refusée laisse
  les décisions non écrites.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy.engine import Engine

from axelcompta.core.rls import appliquer_rls
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.repository import inserer_ecriture
from axelcompta.ledger.service import LedgerService

from .decisions import DecisionHumaine, DecisionRepository
from .decisions_postgres import inserer_decision


class EcrireDecisions(Protocol):
    def ecrire(
        self, decisions: Sequence[DecisionHumaine], reclassements: Sequence[Ecriture]
    ) -> None:
        """Les décisions et leurs OD de reclassement, toutes ou aucune."""
        ...


class PostgresDecisionsEtReclassements:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ecrire(
        self, decisions: Sequence[DecisionHumaine], reclassements: Sequence[Ecriture]
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            for decision in decisions:
                inserer_decision(connexion, decision)
            for ecriture in reclassements:
                inserer_ecriture(connexion, ecriture)


class EnSequence:
    """Deux dépôts distincts, sans transaction commune."""

    def __init__(self, decisions: DecisionRepository, ledger: LedgerService) -> None:
        self._decisions = decisions
        self._ledger = ledger

    def ecrire(
        self, decisions: Sequence[DecisionHumaine], reclassements: Sequence[Ecriture]
    ) -> None:
        for ecriture in reclassements:
            self._ledger.enregistrer(ecriture)
        self._decisions.enregistrer_decisions(decisions)
