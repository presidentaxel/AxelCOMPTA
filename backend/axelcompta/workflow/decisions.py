"""DecisionHumaine et AnnotationDev — doc 17 §9 bloc A, doc 05 §5 précisé.

Deux pistes d'audit distinctes, jamais confondues :
- `DecisionHumaine` : source de vérité comptable/légale. Posée par
  l'utilisateur pro côté client (jamais AxeL, doc 02 §2.3) sur une
  transaction « à trancher » (compte d'attente 471, doc 06 §2).
  **Immuable** : corriger une décision en enregistre une nouvelle qui
  prévaut, jamais une mutation en place — même logique append-only que le
  ledger (doc 06 §1).
- `AnnotationDev` : jugement interne AxeL sur une `DecisionHumaine`
  existante (juste/faux + note), pour le réentraînement du modèle (doc 05
  §5). Ne modifie et ne remplace jamais la décision elle-même.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId

# Une décision plus récente qui annule la précédente : l'écriture redevient
# « à trancher ». On n'efface jamais la ligne (append-only).
CATEGORIE_ANNULATION = "annulation_decision"


def decision_en_vigueur(decision: DecisionHumaine | None) -> DecisionHumaine | None:
    """La décision qui classe encore l'écriture, ou `None` si elle est annulée."""
    if decision is None or decision.categorie == CATEGORIE_ANNULATION:
        return None
    return decision


@dataclass(frozen=True, slots=True)
class DecisionHumaine:
    """Une catégorisation choisie par un humain côté client, sur une
    écriture qui était « à trancher ». `etage_origine`/`confiance_origine`
    gardent trace de ce que le pipeline proposait avant l'intervention —
    utile pour mesurer où l'humain corrige le plus (doc 07 §3.1)."""

    dossier_id: DossierId
    ecriture_id: EcritureId
    categorie: str
    etage_origine: Etage
    confiance_origine: float
    decide_par: UserId
    decide_le: datetime


@dataclass(frozen=True, slots=True)
class AnnotationDev:
    """Jugement interne AxeL sur une `DecisionHumaine`, pour le
    réentraînement — ne réécrit jamais la décision elle-même (doc 05 §5)."""

    dossier_id: DossierId
    ecriture_id: EcritureId
    juste: bool
    note: str
    annote_par: UserId
    annote_le: datetime


class DecisionRepository(ABC):
    """Frontière de persistance pour les décisions humaines et leurs
    annotations dev (doc 18 : seul `workflow` transforme une proposition
    en fait tracé)."""

    @abstractmethod
    def enregistrer_decision(self, decision: DecisionHumaine) -> None:
        """Ajoute une décision. Ne remplace jamais une décision existante
        pour la même écriture : `decision_courante` renvoie la plus
        récente, `lister_decisions` garde tout l'historique."""

    def enregistrer_decisions(self, decisions: Sequence[DecisionHumaine]) -> None:
        """Plusieurs décisions d'un même geste de l'indiv (« tout confirmer »).
        Tout ou rien là où le stockage le permet (Postgres : une transaction)."""
        for decision in decisions:
            self.enregistrer_decision(decision)

    @abstractmethod
    def decision_courante(
        self, dossier_id: DossierId, ecriture_id: EcritureId
    ) -> DecisionHumaine | None:
        """La décision la plus récente pour cette écriture, ou `None` si
        jamais tranchée."""

    @abstractmethod
    def lister_decisions(self, dossier_id: DossierId) -> tuple[DecisionHumaine, ...]:
        """Toutes les décisions d'un dossier, triées par date, historique inclus."""

    @abstractmethod
    def enregistrer_annotation(self, annotation: AnnotationDev) -> None:
        """Ajoute un jugement dev sur une décision existante."""

    @abstractmethod
    def lister_annotations(self, dossier_id: DossierId) -> tuple[AnnotationDev, ...]:
        """Toutes les annotations dev d'un dossier."""
