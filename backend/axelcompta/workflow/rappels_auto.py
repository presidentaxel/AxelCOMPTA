"""Les règles de rappel automatiques partent seules (AXE-808).

Trois déclencheurs, évalués par les tâches planifiées :
* `avant_cloture` : N jours avant la fin de l'exercice du dossier ;
* `a_traiter` : une opération attend une décision depuis N jours ;
* `plateformes_non_reliees` (AXE-890) : aucun compte Uber ou Bolt relié
  dans Rollee ; relance tous les N jours tant que c'est le cas.

« Une seule fois » : une règle ne relance pas un dossier qu'elle a déjà
relancé pour la même raison (depuis l'ouverture de la fenêtre avant
clôture, ou depuis la plus ancienne opération encore à traiter). Pur.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from axelcompta.core.ids import DossierId
from axelcompta.tenants.models import Dossier

DECLENCHEURS_AUTO = ("avant_cloture", "a_traiter", "plateformes_non_reliees")


@dataclass(frozen=True, slots=True)
class Regle:
    id: str
    message: str
    canaux: tuple[str, ...]
    portee: str  # tous | selection
    dossier_ids: tuple[str, ...]
    declencheur: str
    jours: int | None
    actif: bool


@dataclass(frozen=True, slots=True)
class RappelAuto:
    regle_id: str
    dossier_id: DossierId
    message: str
    canaux: tuple[str, ...]


def _vise(regle: Regle, dossier: Dossier) -> bool:
    return regle.portee == "tous" or dossier.id in regle.dossier_ids


def _depuis(
    regle: Regle,
    dossier: Dossier,
    a_traiter_depuis: date | None,
    jour: date,
    sans_plateforme: AbstractSet[DossierId] = frozenset(),
) -> date | None:
    """Le début de la raison de relancer, ou None s'il n'y en a pas."""
    if regle.jours is None or regle.jours < 0:
        return None
    if regle.declencheur == "plateformes_non_reliees":
        # Une fois par fenêtre de N jours, tant qu'aucune plateforme n'est reliée.
        return jour - timedelta(days=regle.jours) if dossier.id in sans_plateforme else None
    if regle.declencheur == "avant_cloture":
        ouverture = dossier.fin_exercice() - timedelta(days=regle.jours)
        return ouverture if ouverture <= jour <= dossier.fin_exercice() else None
    if regle.declencheur == "a_traiter" and a_traiter_depuis is not None:
        return a_traiter_depuis if (jour - a_traiter_depuis).days >= regle.jours else None
    return None


def rappels_a_creer(
    regles: Sequence[Regle],
    dossiers: Sequence[Dossier],
    deja: Mapping[tuple[str, str], Sequence[datetime]],
    a_traiter_depuis: Mapping[DossierId, date],
    jour: date,
    sans_plateforme: AbstractSet[DossierId] = frozenset(),
) -> list[RappelAuto]:
    """`deja` : (règle, dossier) → dates des rappels déjà créés.
    `sans_plateforme` : dossiers sans compte Rollee relié, seulement quand le
    portefeuille a branché Rollee (sinon le chauffeur ne peut rien faire)."""
    a_creer: list[RappelAuto] = []
    for regle in regles:
        if not regle.actif or regle.declencheur not in DECLENCHEURS_AUTO:
            continue
        for dossier in dossiers:
            if not _vise(regle, dossier):
                continue
            depuis = _depuis(
                regle, dossier, a_traiter_depuis.get(dossier.id), jour, sans_plateforme
            )
            if depuis is None:
                continue
            if any(cree.date() >= depuis for cree in deja.get((regle.id, dossier.id), ())):
                continue
            a_creer.append(RappelAuto(regle.id, dossier.id, regle.message, regle.canaux))
    return a_creer
