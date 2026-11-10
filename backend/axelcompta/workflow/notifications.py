"""Notifier l'indiv quand des opérations attendent sa décision (doc 19 §5.2).

Le modèle du produit repose sur un traitement au fil de l'eau, pas sur une
revue de fin d'année : sans ce signal, la file de revue reste vide de
lecteurs. La notification vit dans l'application (cloche de l'espace
chauffeur), pas dans un e-mail : Louis, 2026-09-26, les e-mails et SMS sont
des intégrations que le gestionnaire branche lui-même, pas un canal
d'AxeLCompta. Règles, pensées pour ne pas harceler :

- une seule notification par dossier regroupe tout ce qui attend, jamais une
  par transaction ;
- elle ne se répète que s'il y a des opérations **nouvelles** depuis la
  dernière, et pas avant `INTERVALLE_MIN` ;
- s'il ne s'est rien passé, un rappel unique par `RAPPEL` tant que ça attend ;
- le message ne contient aucun montant ni libellé, seulement le nombre :
  le détail est à un clic, dans l'écran qui l'affiche déjà.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.service import LedgerService

from .decisions import CATEGORIE_ANNULATION, DecisionRepository

TYPE_A_TRANCHER = "a_trancher"
# Exercice terminé, en attente de la validation du chauffeur (doc 06 §5) :
# c'est lui qui clôt, la cloche le lui rappelle.
TYPE_CLOTURE_A_VALIDER = "cloture_a_valider"
COMPTE_ATTENTE = "471"
# Relances de connexion bancaire (`relances_consentement.py`, doc 14 §2.3).
TYPE_CONNEXION_J14 = "connexion_j14"
TYPE_CONNEXION_J7 = "connexion_j7"
TYPE_CONNEXION_EXPIREE = "connexion_expiree"
TYPE_CONNEXION_A_REFAIRE = "connexion_a_refaire"
# AXE-851 : un compte bancaire attend le choix du dirigeant (activité ou
# personnel). Tant qu'il n'a pas choisi, la synchro écarte ses opérations.
TYPE_COMPTES_A_CHOISIR = "comptes_a_choisir"
# TVA en cours d'année (AXE-805) : la CA3 de la période est à déposer.
TYPE_TVA_J7 = "tva_j7"
TYPE_TVA_J2 = "tva_j2"
MESSAGES_FIXES = {
    TYPE_TVA_J7: "Votre déclaration de TVA est à déposer dans une semaine : voyez Ma TVA.",
    TYPE_TVA_J2: "Votre déclaration de TVA est à déposer dans deux jours : voyez Ma TVA.",
    TYPE_CLOTURE_A_VALIDER: "Votre exercice est terminé : relisez-le et validez sa clôture.",
    TYPE_CONNEXION_J14: (
        "Votre connexion bancaire expire dans deux semaines : renouvelez-la pour que "
        "vos opérations continuent d'arriver."
    ),
    TYPE_CONNEXION_J7: (
        "Votre connexion bancaire expire dans une semaine : renouvelez-la pour que "
        "vos opérations continuent d'arriver."
    ),
    TYPE_CONNEXION_EXPIREE: (
        "Votre connexion bancaire a expiré : vos opérations ne sont plus synchronisées. "
        "Renouvelez-la."
    ),
    TYPE_CONNEXION_A_REFAIRE: (
        "Votre banque demande de confirmer la connexion : vos opérations ne sont plus "
        "synchronisées. Confirmez-la."
    ),
}
INTERVALLE_MIN = timedelta(hours=6)
RAPPEL = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class NotificationEnvoyee:
    id: str
    dossier_id: DossierId
    type: str
    envoye_le: datetime
    ecriture_ids: tuple[EcritureId, ...]
    lue_le: datetime | None = None

    @property
    def message(self) -> str:
        """Formulation figée à l'envoi (les écritures alors en attente).
        La cloche passe par `texte_cloche`, qui recalcule le nombre."""
        if self.type in MESSAGES_FIXES:
            return MESSAGES_FIXES[self.type]
        return message(len(self.ecriture_ids))


class NotificationRepository(ABC):
    @abstractmethod
    def derniere(self, dossier_id: DossierId, type_: str) -> NotificationEnvoyee | None: ...

    @abstractmethod
    def enregistrer(self, notification: NotificationEnvoyee) -> None: ...

    @abstractmethod
    def lister(self, dossier_id: DossierId, limite: int) -> list[NotificationEnvoyee]:
        """Les plus récentes d'abord."""

    @abstractmethod
    def marquer_lues(self, dossier_id: DossierId, maintenant: datetime) -> int:
        """Marque lues toutes celles qui ne l'étaient pas ; renvoie leur nombre."""

    @abstractmethod
    def marquer_lue(
        self, dossier_id: DossierId, notification_id: str, maintenant: datetime
    ) -> bool:
        """Marque lue cette notification. False si elle n'appartient pas au dossier.
        Déjà lue : ne change pas l'instant, et renvoie True."""


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self.historique: list[NotificationEnvoyee] = []

    def derniere(self, dossier_id: DossierId, type_: str) -> NotificationEnvoyee | None:
        candidates = [n for n in self.historique if n.dossier_id == dossier_id and n.type == type_]
        return max(candidates, key=lambda n: n.envoye_le, default=None)

    def enregistrer(self, notification: NotificationEnvoyee) -> None:
        self.historique.append(notification)

    def lister(self, dossier_id: DossierId, limite: int) -> list[NotificationEnvoyee]:
        du_dossier = [n for n in self.historique if n.dossier_id == dossier_id]
        return sorted(du_dossier, key=lambda n: n.envoye_le, reverse=True)[:limite]

    def marquer_lues(self, dossier_id: DossierId, maintenant: datetime) -> int:
        nb = 0
        for i, n in enumerate(self.historique):
            if n.dossier_id == dossier_id and n.lue_le is None:
                self.historique[i] = replace(n, lue_le=maintenant)
                nb += 1
        return nb

    def marquer_lue(
        self, dossier_id: DossierId, notification_id: str, maintenant: datetime
    ) -> bool:
        for i, notification in enumerate(self.historique):
            if notification.id != notification_id or notification.dossier_id != dossier_id:
                continue
            if notification.lue_le is None:
                self.historique[i] = replace(notification, lue_le=maintenant)
            return True
        return False


def ecritures_a_trancher(
    ledger: LedgerService, decisions: DecisionRepository, dossier_id: DossierId
) -> tuple[EcritureId, ...]:
    """Écritures au compte d'attente sans décision en vigueur, hors paires
    originale + contre-passation. Une annulation rend l'écriture à nouveau
    comptable : seule la dernière décision compte."""
    ecritures = ledger.grand_livre(dossier_id)
    dernieres: dict[EcritureId, str] = {}
    for decision in decisions.lister_decisions(dossier_id):
        dernieres[decision.ecriture_id] = decision.categorie
    exclues = {
        ecriture_id
        for ecriture_id, categorie in dernieres.items()
        if categorie != CATEGORIE_ANNULATION
    } | annulees(ecritures)
    return tuple(
        e.id
        for e in ecritures
        if e.id not in exclues and any(ligne.compte == COMPTE_ATTENTE for ligne in e.lignes)
    )


@dataclass(frozen=True, slots=True)
class ResultatNotification:
    dossier_id: DossierId
    statut: str  # creee | rien_a_faire | deja_notifie | echec
    nb_a_trancher: int = 0
    detail: str | None = None
    type: str = TYPE_A_TRANCHER


def message(nb: int) -> str:
    """Deux textes distincts plutôt qu'un gabarit à trous, pour que le
    singulier se lise naturellement. « À traiter », comme l'onglet."""
    if nb == 1:
        return "Une opération est à traiter"
    return f"{nb} opérations sont à traiter"


def sujet(type_: str) -> str:
    """Les paliers bancaires (J-14, J-7, expiré, à refaire) sont un seul
    sujet : le dernier remplace les précédents dans la cloche."""
    if type_.startswith("connexion"):
        return "connexion"
    if type_.startswith("tva_"):
        return "tva"
    return type_


def regrouper(
    notifications: Sequence[NotificationEnvoyee],
) -> tuple[NotificationEnvoyee, ...]:
    """Le plus récent de chaque sujet. Les rappels ne s'empilent pas."""
    retenus: dict[str, NotificationEnvoyee] = {}
    for notification in sorted(notifications, key=lambda n: n.envoye_le, reverse=True):
        retenus.setdefault(sujet(notification.type), notification)
    return tuple(sorted(retenus.values(), key=lambda n: n.envoye_le, reverse=True))


def message_comptes_a_choisir(nb: int) -> str:
    if nb == 1:
        return "Un compte bancaire attend votre choix : sert-il à votre activité ?"
    return f"{nb} comptes bancaires attendent votre choix : servent-ils à votre activité ?"


def texte_cloche(
    notification: NotificationEnvoyee, nb_a_trancher: int, comptes_a_choisir: int = 0
) -> str | None:
    """Texte affiché. Les nombres sont ceux du moment : ceux de l'envoi
    resteraient après traitement. Zéro : on n'affiche pas, pour ne pas
    ouvrir un écran « Tout est à jour »."""
    if notification.type == TYPE_A_TRANCHER:
        if nb_a_trancher < 1:
            return None
        return message(nb_a_trancher)
    if notification.type == TYPE_COMPTES_A_CHOISIR:
        if comptes_a_choisir < 1:
            return None
        return message_comptes_a_choisir(comptes_a_choisir)
    if notification.type in MESSAGES_FIXES:
        return MESSAGES_FIXES[notification.type]
    return None


@dataclass(frozen=True, slots=True)
class NotificationCloche:
    id: str
    type: str
    message: str
    envoye_le: datetime
    lue: bool


def pour_la_cloche(
    notifications: Sequence[NotificationEnvoyee],
    nb_a_trancher: int,
    limite: int,
    comptes_a_choisir: int = 0,
) -> tuple[NotificationCloche, ...]:
    """Ce que la cloche montre : un sujet, un texte à jour, au plus `limite`."""
    affichees: list[NotificationCloche] = []
    for notification in regrouper(notifications):
        texte = texte_cloche(notification, nb_a_trancher, comptes_a_choisir)
        if texte is None:
            continue
        affichees.append(
            NotificationCloche(
                id=notification.id,
                type=notification.type,
                message=texte,
                envoye_le=notification.envoye_le,
                lue=notification.lue_le is not None,
            )
        )
        if len(affichees) >= limite:
            break
    return tuple(affichees)


def notifier_a_trancher(
    dossier_id: DossierId,
    ledger: LedgerService,
    decisions: DecisionRepository,
    notifications: NotificationRepository,
    maintenant: datetime,
) -> ResultatNotification:
    en_attente = ecritures_a_trancher(ledger, decisions, dossier_id)
    if not en_attente:
        return ResultatNotification(dossier_id, "rien_a_faire")

    derniere = notifications.derniere(dossier_id, TYPE_A_TRANCHER)
    if derniere is not None:
        age = maintenant - derniere.envoye_le
        nouvelles = set(en_attente) - set(derniere.ecriture_ids)
        a_notifier = (bool(nouvelles) and age >= INTERVALLE_MIN) or age >= RAPPEL
        if not a_notifier:
            return ResultatNotification(dossier_id, "deja_notifie", len(en_attente))

    notifications.enregistrer(
        NotificationEnvoyee(
            id=uuid.uuid4().hex,
            dossier_id=dossier_id,
            type=TYPE_A_TRANCHER,
            envoye_le=maintenant,
            ecriture_ids=en_attente,
        )
    )
    return ResultatNotification(dossier_id, "creee", len(en_attente))


def notifier_cloture_a_valider(
    dossier_id: DossierId,
    fin_exercice: date,
    notifications: NotificationRepository,
    maintenant: datetime,
) -> ResultatNotification:
    """Tant que l'exercice terminé n'est pas clos : une notification, puis un
    rappel par `RAPPEL`. Clore déplace l'exercice du dossier, ce qui arrête
    les rappels d'eux-mêmes."""
    if fin_exercice >= maintenant.date():
        return ResultatNotification(dossier_id, "rien_a_faire", type=TYPE_CLOTURE_A_VALIDER)
    derniere = notifications.derniere(dossier_id, TYPE_CLOTURE_A_VALIDER)
    if derniere is not None and (
        derniere.envoye_le.date() > fin_exercice and maintenant - derniere.envoye_le < RAPPEL
    ):
        return ResultatNotification(dossier_id, "deja_notifie", type=TYPE_CLOTURE_A_VALIDER)
    notifications.enregistrer(
        NotificationEnvoyee(
            id=uuid.uuid4().hex,
            dossier_id=dossier_id,
            type=TYPE_CLOTURE_A_VALIDER,
            envoye_le=maintenant,
            ecriture_ids=(),
        )
    )
    return ResultatNotification(dossier_id, "creee", type=TYPE_CLOTURE_A_VALIDER)


def notifier_comptes_a_choisir(
    dossier_id: DossierId,
    nb_comptes: int,
    notifications: NotificationRepository,
    maintenant: datetime,
) -> ResultatNotification:
    """AXE-851. Une notification dès qu'un compte attend le choix du
    dirigeant, puis un rappel par `RAPPEL` tant qu'il attend. Choisir vide
    le compteur, ce qui arrête les rappels d'eux-mêmes."""
    if nb_comptes < 1:
        return ResultatNotification(dossier_id, "rien_a_faire", type=TYPE_COMPTES_A_CHOISIR)
    derniere = notifications.derniere(dossier_id, TYPE_COMPTES_A_CHOISIR)
    if derniere is not None and maintenant - derniere.envoye_le < RAPPEL:
        return ResultatNotification(dossier_id, "deja_notifie", type=TYPE_COMPTES_A_CHOISIR)
    notifications.enregistrer(
        NotificationEnvoyee(
            id=uuid.uuid4().hex,
            dossier_id=dossier_id,
            type=TYPE_COMPTES_A_CHOISIR,
            envoye_le=maintenant,
            ecriture_ids=(),
        )
    )
    return ResultatNotification(dossier_id, "creee", type=TYPE_COMPTES_A_CHOISIR)
