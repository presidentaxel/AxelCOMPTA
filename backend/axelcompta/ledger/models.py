"""Objets du domaine comptable (doc 06 §2). Squelette de structure — les
invariants (équilibre débit/crédit, immutabilité) ne sont pas encore
appliqués ici, seulement documentés.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money


class Journal(Enum):
    """Journaux V1 (doc 06 §2)."""

    BQ = auto()  # banque
    AC = auto()  # achats
    VE = auto()  # ventes
    OD = auto()  # opérations diverses
    AN = auto()  # à-nouveaux


class Sens(Enum):
    DEBIT = auto()
    CREDIT = auto()


@dataclass(frozen=True, slots=True)
class LigneEcriture:
    """Une ligne d'écriture : compte, sens, montant, analytique, code TVA."""

    compte: str  # numéro de compte PCG
    sens: Sens
    montant: Money
    analytique: str | None = None
    code_tva: str | None = None


@dataclass(frozen=True, slots=True)
class Ecriture:
    """En-tête + lignes (doc 06 §2). Invariant à faire respecter (hors squelette) :
    somme des débits == somme des crédits, ou rejet — jamais persisté déséquilibré
    (doc 06 §1).
    """

    id: EcritureId
    dossier_id: DossierId
    journal: Journal
    date: date
    libelle: str
    reference_piece: str | None
    lignes: tuple[LigneEcriture, ...]
    # Numéro dans la séquence de l'exercice et horodatage de validation,
    # posés par la base à l'insertion (AXE-807, I3). `None` tant que
    # l'écriture n'est pas en base (calculée, ou grand livre en mémoire).
    # Hors comparaison : une écriture relue égale celle qu'on a écrite.
    numero: int | None = field(default=None, compare=False)
    valide_le: datetime | None = field(default=None, compare=False)
