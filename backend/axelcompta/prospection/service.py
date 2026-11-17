"""Recevoir une demande d'échange et prévenir l'équipe (AXE-949).

Deux temps, pour qu'une panne de Slack ne perde jamais une demande :

1. `recevoir` valide et enregistre, dans la requête du visiteur ;
2. `notifier` prévient l'équipe, après la réponse. Un échec est noté, et
   `relancer` (tâches planifiées, chaque heure) réessaie jusqu'à
   `TENTATIVES_MAX` fois, puis le dit à Sentry.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from axelcompta.prospection.models import DemandeEchange, TropDeDemandes, preparer_demande
from axelcompta.prospection.repository import DemandesRepository
from axelcompta.prospection.slack import Notifieur

logger = logging.getLogger(__name__)

# La même adresse qui renvoie le formulaire dans ce délai n'ajoute rien :
# un double clic ne prévient pas l'équipe deux fois.
FENETRE_DOUBLON = timedelta(minutes=15)
FENETRE_PLAFOND = timedelta(hours=1)
PLAFOND_PAR_HEURE = 30
TENTATIVES_MAX = 3
# `relancer` laisse un peu de temps à la première notification, qui part
# juste après la réponse.
DELAI_AVANT_RELANCE = timedelta(minutes=5)
LIMITE_PAR_PASSAGE = 20


def recevoir(
    depot: DemandesRepository,
    *,
    id: str,  # noqa: A002
    nom: str,
    email: str,
    organisation: str,
    role: str,
    message: str | None,
    piege: str,
    maintenant: datetime,
) -> DemandeEchange | None:
    """Enregistre la demande. Rend `None` quand il n'y a rien à notifier :
    champ piège rempli (un robot), ou même adresse déjà reçue à l'instant.
    Dans les deux cas le visiteur reçoit la même réponse qu'une demande reçue.
    """
    if piege.strip():
        return None
    demande = preparer_demande(
        id=id,
        nom=nom,
        email=email,
        organisation=organisation,
        role=role,
        message=message,
        cree_le=maintenant,
    )
    if depot.email_recu_depuis(demande.email, maintenant - FENETRE_DOUBLON):
        return None
    if depot.nombre_depuis(maintenant - FENETRE_PLAFOND) >= PLAFOND_PAR_HEURE:
        raise TropDeDemandes("Trop de demandes pour le moment. Réessayez dans quelques minutes.")
    depot.ajouter(demande)
    return demande


def _raison(exc: Exception) -> str:
    """Ce qui est gardé d'un échec : jamais le message de l'exception, qui
    contient l'adresse du webhook."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Slack a répondu {exc.response.status_code}"
    return type(exc).__name__


def notifier(
    depot: DemandesRepository,
    notifieur: Notifieur | None,
    demande: DemandeEchange,
    maintenant: datetime,
) -> bool:
    """Prévient l'équipe. Sans webhook, la demande reste en attente, sans
    compter d'essai : elle partira dès que le webhook sera posé."""
    if notifieur is None:
        return False
    try:
        notifieur.notifier(demande)
    except Exception as exc:  # noqa: BLE001 — la demande est gardée, `relancer` réessaiera
        raison = _raison(exc)
        depot.noter_echec(demande.id, raison)
        if demande.tentatives + 1 >= TENTATIVES_MAX:
            logger.error("Demande d'échange %s : équipe non prévenue (%s)", demande.id, raison)
        return False
    depot.marquer_notifiee(demande.id, maintenant)
    return True


def relancer(depot: DemandesRepository, notifieur: Notifieur | None, maintenant: datetime) -> str:
    """Un passage des tâches planifiées. Rend une ligne pour le bilan."""
    en_attente = depot.non_notifiees(
        maintenant - DELAI_AVANT_RELANCE, TENTATIVES_MAX, LIMITE_PAR_PASSAGE
    )
    if not en_attente:
        return "demandes d'échange : rien en attente"
    if notifieur is None:
        return f"demandes d'échange : {len(en_attente)} en attente, aucun webhook Slack"
    envoyees = sum(notifier(depot, notifieur, d, maintenant) for d in en_attente)
    return f"demandes d'échange : {envoyees} notifiée(s) sur {len(en_attente)}"
