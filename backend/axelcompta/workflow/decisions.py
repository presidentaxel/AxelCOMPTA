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
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId

# Une décision plus récente qui annule la précédente : l'écriture redevient
# « à trancher ». On n'efface jamais la ligne (append-only).
CATEGORIE_ANNULATION = "annulation_decision"
# « Je ne sais plus » (AXE-844, retrait d'espèces) : la réponse est gardée,
# l'opération reste au compte d'attente et passe à l'expert-comptable.
CATEGORIE_A_PRECISER = "a_preciser_expert"


def decision_en_vigueur(decision: DecisionHumaine | None) -> DecisionHumaine | None:
    """La décision qui classe encore l'écriture, ou `None` si elle est annulée."""
    if decision is None or decision.categorie == CATEGORIE_ANNULATION:
        return None
    return decision


# Nature d'une décision par rapport à ce qui était proposé (AXE-871).
NATURE_CONFIRMEE = "confirmee"
NATURE_CORRIGEE = "corrigee"
NATURE_SANS_PROPOSITION = "sans_proposition"
_SANS_AVIS = frozenset({"", "non_categorise_a_verifier"})


@dataclass(frozen=True, slots=True)
class ContexteDecision:
    """Ce que l'humain avait sous les yeux en décidant (AXE-871) : de quoi
    réentraîner le modèle et mesurer chaque étage sans relire le grand
    livre, qui peut avoir bougé depuis. Le décideur (chauffeur, gestionnaire,
    expert) se retrouve par `decide_par`."""

    libelle: str
    montant_cts: int  # signé, façon relevé : négatif = dépense
    moyen_paiement: str | None
    proposee: str | None  # catégorie proposée à ce moment-là
    etage_propose: str | None
    confiance_proposee: float | None
    nature: str  # NATURE_CONFIRMEE | NATURE_CORRIGEE | NATURE_SANS_PROPOSITION

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def depuis_dict(brut: dict[str, Any]) -> ContexteDecision:
        confiance = brut.get("confiance_proposee")
        return ContexteDecision(
            libelle=str(brut.get("libelle", "")),
            montant_cts=int(brut.get("montant_cts", 0)),
            moyen_paiement=brut.get("moyen_paiement"),
            proposee=brut.get("proposee"),
            etage_propose=brut.get("etage_propose"),
            confiance_proposee=float(confiance) if confiance is not None else None,
            nature=str(brut.get("nature", NATURE_SANS_PROPOSITION)),
        )


def nature_decision(proposee: str | None, choisie: str) -> str:
    if proposee is None or proposee in _SANS_AVIS:
        return NATURE_SANS_PROPOSITION
    return NATURE_CONFIRMEE if proposee == choisie else NATURE_CORRIGEE


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
    # AXE-871 : `None` pour les décisions d'avant le 12/11/2026.
    contexte: ContexteDecision | None = None


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
