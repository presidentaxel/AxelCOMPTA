"""Pipeline hybride à étages (doc 05 §1) : l'interface.

Implémentation en place : `rules_and_ml.RulesAndMlPipeline` (virements
internes, règles, ML, catégorie de la banque). Pas de LLM d'arbitrage : la
porte existe dans `pseudonymize/`, aucun fournisseur n'est branché.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.providers.base import NormalizedTransaction

from .models import ProposedEntry


class CategorizationPipeline(ABC):
    @abstractmethod
    def categoriser(
        self,
        dossier_id: DossierId,
        transaction: NormalizedTransaction,
    ) -> ProposedEntry:
        """Fait traverser les étages (doc 05 §1) jusqu'à obtenir une proposition."""

    def categoriser_lot(
        self, dossier_id: DossierId, transactions: Sequence[NormalizedTransaction]
    ) -> list[ProposedEntry]:
        """Un lot entier, dans l'ordre. Par défaut ligne par ligne ; une
        implémentation qui regarde les opérations ensemble (virements
        internes, AXE-826) le surcharge."""
        return [self.categoriser(dossier_id, transaction) for transaction in transactions]
