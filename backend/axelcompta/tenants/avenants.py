"""Changements de régime d'imposition par avenant daté (doc 06 §7).

Un changement de régime ne réécrit jamais la configuration passée : c'est
un avenant, ajouté à un historique append-only, qui prend effet à partir
d'un exercice. La configuration du dossier reste celle de son exercice en
cours ; `regime_pour_exercice` dit quel régime s'applique à n'importe quel
exercice, passé ou à venir.

Cas porté ici : la fin de l'option IR temporaire (art. 239 bis AB CGI,
5 exercices). Les tâches planifiées enregistrent d'elles-mêmes, dès le
dernier exercice couvert, la bascule à l'IS de l'exercice suivant ; elle
est visible du chauffeur et du gestionnaire avant de s'appliquer.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from axelcompta.core.ids import DossierId

from .models import Dossier
from .statuts import DUREE_OPTION_IR, RegimeImposition

AUTEUR_SYSTEME = "systeme"


class MotifAvenant(StrEnum):
    FIN_OPTION_IR = "fin_option_ir"
    RENONCIATION_OPTION_IR = "renonciation_option_ir"


@dataclass(frozen=True, slots=True)
class AvenantRegime:
    id: str
    dossier_id: DossierId
    exercice_effet: int  # année du premier exercice concerné
    regime_imposition: RegimeImposition
    option_ir_debut: int | None
    motif: MotifAvenant
    enregistre_le: datetime
    enregistre_par: str


class AvenantRegimeRepository(ABC):
    @abstractmethod
    def enregistrer(self, avenant: AvenantRegime) -> None:
        """Ajoute, ne modifie jamais (historique append-only)."""

    @abstractmethod
    def lister(self, dossier_id: DossierId) -> tuple[AvenantRegime, ...]:
        """Par exercice d'effet croissant."""


class InMemoryAvenantRegimeRepository(AvenantRegimeRepository):
    def __init__(self) -> None:
        self._avenants: list[AvenantRegime] = []

    def enregistrer(self, avenant: AvenantRegime) -> None:
        self._avenants.append(avenant)

    def lister(self, dossier_id: DossierId) -> tuple[AvenantRegime, ...]:
        return tuple(
            sorted(
                (a for a in self._avenants if a.dossier_id == dossier_id),
                key=lambda a: (a.exercice_effet, a.enregistre_le),
            )
        )


def regime_pour_exercice(
    dossier: Dossier, avenants: tuple[AvenantRegime, ...], annee: int
) -> tuple[str, int | None]:
    """(régime, année de début d'option IR) applicable à l'exercice `annee` :
    le dernier avenant en vigueur, sinon la configuration du dossier."""
    en_vigueur = [a for a in avenants if a.exercice_effet <= annee]
    if not en_vigueur:
        return dossier.regime_imposition, dossier.option_ir_debut
    dernier = max(en_vigueur, key=lambda a: (a.exercice_effet, a.enregistre_le))
    return dernier.regime_imposition.value, dernier.option_ir_debut


def rang_option_ir(dossier: Dossier) -> int | None:
    """Rang de l'exercice en cours dans l'option IR (1 à 5), `None` hors
    option."""
    if dossier.regime_imposition != RegimeImposition.OPTION_IR or dossier.option_ir_debut is None:
        return None
    return dossier.exercice_debut.year - dossier.option_ir_debut + 1


def alerte_option_ir(dossier: Dossier) -> str | None:
    """Alerte à l'approche du terme : avant-dernier (N-1) et dernier (N)
    exercice couverts par l'option."""
    rang = rang_option_ir(dossier)
    if rang is None or dossier.option_ir_debut is None:
        return None
    passage_is = dossier.option_ir_debut + DUREE_OPTION_IR
    if rang == DUREE_OPTION_IR:
        return (
            "Dernier exercice couvert par l'option pour l'impôt sur le revenu : "
            f"la société passe à l'impôt sur les sociétés pour l'exercice {passage_is}."
        )
    if rang == DUREE_OPTION_IR - 1:
        return (
            "Avant-dernier exercice couvert par l'option pour l'impôt sur le revenu : "
            f"la société passera à l'impôt sur les sociétés pour l'exercice {passage_is}."
        )
    return None


def programmer_bascule(
    dossier: Dossier, avenants: tuple[AvenantRegime, ...], maintenant: datetime
) -> AvenantRegime | None:
    """Au dernier exercice de l'option, l'avenant qui passe la société à
    l'IS à l'exercice suivant. `None` s'il n'y a rien à faire ou s'il est
    déjà enregistré (idempotent : relancé toutes les heures)."""
    if rang_option_ir(dossier) != DUREE_OPTION_IR or dossier.option_ir_debut is None:
        return None
    effet = dossier.option_ir_debut + DUREE_OPTION_IR
    if any(
        a.exercice_effet <= effet and a.regime_imposition is RegimeImposition.IS for a in avenants
    ):
        return None
    return AvenantRegime(
        id=uuid.uuid4().hex,
        dossier_id=dossier.id,
        exercice_effet=effet,
        regime_imposition=RegimeImposition.IS,
        option_ir_debut=None,
        motif=MotifAvenant.FIN_OPTION_IR,
        enregistre_le=maintenant,
        enregistre_par=AUTEUR_SYSTEME,
    )


def a_venir(dossier: Dossier, avenants: tuple[AvenantRegime, ...]) -> tuple[AvenantRegime, ...]:
    """Avenants qui prennent effet après l'exercice en cours."""
    return tuple(a for a in avenants if a.exercice_effet > dossier.exercice_debut.year)


def programmer_bascules(
    dossiers: tuple[Dossier, ...], depot: AvenantRegimeRepository, maintenant: datetime
) -> list[AvenantRegime]:
    """Toutes les bascules dues d'un portefeuille, enregistrées ; renvoie
    celles qui viennent d'être ajoutées."""
    ajoutes: list[AvenantRegime] = []
    for dossier in dossiers:
        avenant = programmer_bascule(dossier, depot.lister(dossier.id), maintenant)
        if avenant is not None:
            depot.enregistrer(avenant)
            ajoutes.append(avenant)
    return ajoutes
