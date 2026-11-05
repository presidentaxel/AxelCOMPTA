"""Façade publique de ledger/ — la seule chose que `api` a le droit d'importer
(doc 03 §3). Squelette : signatures uniquement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.periodes import Periode


class LedgerService(ABC):
    """Invariants doc 06 §1 à faire respecter par toute implémentation :
    équilibre débit/crédit obligatoire, immutabilité (contre-passation, jamais
    de modification d'une écriture validée).
    """

    @abstractmethod
    def enregistrer(self, ecriture: Ecriture) -> EcritureId:
        """Valide l'équilibre et la période (I4) puis persiste l'écriture, ou
        lève une erreur typée (`PeriodeClose` pour un exercice clos)."""

    @abstractmethod
    def periodes_closes(self, dossier_id: DossierId) -> tuple[Periode, ...]:
        """Exercices clos du dossier, (début, fin) inclus."""

    @abstractmethod
    def grand_livre(self, dossier_id: DossierId) -> tuple[Ecriture, ...]:
        """Toutes les écritures validées d'un dossier, triées par date."""
