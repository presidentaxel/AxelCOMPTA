"""L'expert-comptable prend la responsabilité juridique de ses changements (AXE-800).

Décision de Louis (5 nov.) : le mode expert vise une entreprise qui gère sa
flotte avec un expert-comptable. C'est lui qui décide d'une imputation,
jamais le logiciel ; AxeL reste éditeur (doc 02 §2.3). Il faut donc que la
personne qui change une écriture en prenne la charge, de façon prouvable :

* **habilitation** : un admin du portefeuille déclare l'expert (nom,
  cabinet, inscription à l'Ordre, lettre de mission et dossiers couverts).
  Déclaratif (pas d'API publique de l'Ordre), tracé, jamais modifié : une
  nouvelle habilitation remplace la précédente ;
* **engagement** : l'expert accepte un texte versionné, gardé mot pour mot
  avec la date et l'adresse IP. Sans lui, le rôle ne s'active pas ;
* **décision** : chaque imputation, annulation ou qualification d'anomalie
  porte l'auteur, le motif (obligatoire) et la version de l'engagement. Une
  imputation s'écrit avec ses écritures, tout ou rien (I6).

Ce module est pur : la persistance est derrière `ExpertRepository`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal, Protocol

from axelcompta.core.errors import Interdit, SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId, TenantId, UserId
from axelcompta.ledger.models import Ecriture
from axelcompta.ledger.service import LedgerService

ROLE_EXPERT = "expert_comptable"

# Texte à faire relire par un juriste avant le pilote (AXE-813). Toute
# modification change la version : chaque expert l'accepte à nouveau.
VERSION_ENGAGEMENT = "2026-11-09"
TEXTE_ENGAGEMENT = (
    "Je, expert-comptable inscrit au tableau de l'Ordre, décide seul et sous ma "
    "responsabilité de chaque imputation, annulation ou qualification que je passe "
    "dans les dossiers couverts par ma lettre de mission. AxeLCompta est un outil : "
    "il ne décide d'aucune écriture et ne vérifie pas mes choix. Chacun de mes "
    "changements porte mon nom, son motif et la date ; je ne passe pas de changement "
    "sans motif."
)

Nature = Literal["imputation", "annulation", "qualification"]
LONGUEUR_MIN_MOTIF = 3


class ExpertNonHabilite(Interdit):
    """Rôle, habilitation, engagement ou lettre de mission manquant."""


class MotifManquant(SaisieInvalide):
    """Un changement d'expert sans motif."""


@dataclass(frozen=True, slots=True)
class Habilitation:
    tenant_id: TenantId
    email: str
    nom: str
    cabinet: str
    numero_ordre: str
    lettre_mission: str  # référence de la lettre de mission
    date_lettre: date
    dossiers: tuple[DossierId, ...]
    accordee_par: UserId
    accordee_le: datetime


@dataclass(frozen=True, slots=True)
class Engagement:
    tenant_id: TenantId
    email: str
    version: str
    texte: str
    adresse: str  # IP et navigateur au moment de l'acceptation
    acteur: UserId
    accepte_le: datetime


@dataclass(frozen=True, slots=True)
class DecisionExpert:
    id: str
    tenant_id: TenantId
    dossier_id: DossierId
    ecriture_id: EcritureId | None  # l'opération concernée, s'il y en a une
    nature: Nature
    motif: str
    auteur: UserId
    auteur_nom: str
    version_engagement: str
    le: datetime
    ecritures: tuple[EcritureId, ...] = ()  # écrites avec la décision


class ExpertRepository(Protocol):
    def habilitation(self, tenant_id: TenantId, email: str) -> Habilitation | None:
        """La plus récente, ou `None`."""
        ...

    def habiliter(self, habilitation: Habilitation) -> None: ...

    def engagement(self, tenant_id: TenantId, email: str) -> Engagement | None:
        """Le plus récent, ou `None`."""
        ...

    def accepter(self, engagement: Engagement) -> None: ...

    def decider(self, decision: DecisionExpert, ecritures: Sequence[Ecriture]) -> None:
        """La décision et ses écritures, dans une seule transaction."""
        ...

    def decisions(self, dossier_id: DossierId) -> tuple[DecisionExpert, ...]: ...


@dataclass(frozen=True, slots=True)
class ExpertActif:
    """Ce que l'API sait de l'expert une fois tout vérifié."""

    habilitation: Habilitation
    engagement: Engagement

    def couvre(self, dossier_id: DossierId) -> bool:
        return dossier_id in self.habilitation.dossiers


def expert_actif(
    role: str | None, habilitation: Habilitation | None, engagement: Engagement | None
) -> ExpertActif:
    """Lève `ExpertNonHabilite` avec la raison, dans l'ordre où l'expert la
    lèvera : rôle, habilitation, engagement à la version en vigueur."""
    if role != ROLE_EXPERT:
        raise ExpertNonHabilite(
            "Réservé à l'expert-comptable du portefeuille : le gestionnaire voit les agrégats."
        )
    if habilitation is None:
        raise ExpertNonHabilite("Aucune habilitation : un administrateur doit vous déclarer.")
    if engagement is None or engagement.version != VERSION_ENGAGEMENT:
        raise ExpertNonHabilite("Acceptez l'engagement de responsabilité pour continuer.")
    return ExpertActif(habilitation, engagement)


def exiger_dossier(actif: ExpertActif, dossier_id: DossierId) -> None:
    if not actif.couvre(dossier_id):
        raise ExpertNonHabilite("Ce dossier n'est pas couvert par votre lettre de mission.")


def motif_valide(motif: str) -> str:
    propre = " ".join(motif.split())
    if len(propre) < LONGUEUR_MIN_MOTIF:
        raise MotifManquant("Indiquez le motif de ce changement.")
    return propre


def verifier_engagement(texte: str, version: str) -> None:
    """L'expert accepte le texte affiché, mot pour mot, à la version en vigueur."""
    if version != VERSION_ENGAGEMENT or texte != TEXTE_ENGAGEMENT:
        raise SaisieInvalide("Le texte accepté ne correspond pas à l'engagement en vigueur.")


class ExpertMemoire:
    """Pour les tests. Les écritures vont au ledger donné, avant la décision :
    une écriture refusée (I1, I4) ne laisse pas de décision."""

    def __init__(self, ledger: LedgerService) -> None:
        self._ledger = ledger
        self.habilitations: list[Habilitation] = []
        self.engagements: list[Engagement] = []
        self.liste_decisions: list[DecisionExpert] = []

    def habilitation(self, tenant_id: TenantId, email: str) -> Habilitation | None:
        trouvees = [
            h for h in self.habilitations if h.tenant_id == tenant_id and h.email == email.lower()
        ]
        return max(trouvees, key=lambda h: h.accordee_le, default=None)

    def habiliter(self, habilitation: Habilitation) -> None:
        self.habilitations.append(replace(habilitation, email=habilitation.email.lower()))

    def engagement(self, tenant_id: TenantId, email: str) -> Engagement | None:
        trouves = [
            e for e in self.engagements if e.tenant_id == tenant_id and e.email == email.lower()
        ]
        return max(trouves, key=lambda e: e.accepte_le, default=None)

    def accepter(self, engagement: Engagement) -> None:
        self.engagements.append(replace(engagement, email=engagement.email.lower()))

    def decider(self, decision: DecisionExpert, ecritures: Sequence[Ecriture]) -> None:
        for ecriture in ecritures:
            self._ledger.enregistrer(ecriture)
        self.liste_decisions.append(replace(decision, ecritures=tuple(e.id for e in ecritures)))

    def decisions(self, dossier_id: DossierId) -> tuple[DecisionExpert, ...]:
        return tuple(d for d in self.liste_decisions if d.dossier_id == dossier_id)
