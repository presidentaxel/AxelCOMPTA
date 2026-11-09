"""ProposedEntry — sortie du pipeline de catégorisation, avant validation par
`workflow` et écriture réelle via `ledger` (doc 03 §3, doc 05).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from axelcompta.core.ids import DossierId, TransactionId


class Etage(Enum):
    """Quel étage du pipeline a produit la proposition (doc 05 §1)."""

    REGLE = auto()
    ML = auto()
    # Catégorie donnée par la banque (Bridge) : un indice, qui propose sans
    # jamais imputer seul (AXE-826).
    BANQUE = auto()
    LLM = auto()
    REVUE_HUMAINE = auto()


@dataclass(frozen=True, slots=True)
class ProposedEntry:
    """Une catégorisation proposée pour une transaction, pas encore une écriture.

    À faire (hors squelette) : le template d'écriture réel se construit à
    partir de `categorie` + le pack du dossier (doc 06 §3) — pas ici.
    """

    dossier_id: DossierId
    transaction_id: TransactionId
    categorie: str
    etage: Etage
    confiance: float  # [0.0, 1.0] ; calibrée (chance d'avoir raison) si le modèle l'est
    # Confiance à partir de laquelle cette proposition peut s'imputer sans
    # regard humain, propre à sa catégorie (`ml_fallback.Calibration`) ;
    # `inf` : jamais ; `None` : seuils historiques de `workflow/synchro.py`.
    seuil_imputation: float | None = None
    # Comment l'argent est sorti ou entré (carte, virement, prélèvement,
    # retrait), tel que la banque le dit (AXE-836). Gardé avec la
    # proposition : c'est le contexte de l'opération au moment du classement.
    moyen_paiement: str | None = None
