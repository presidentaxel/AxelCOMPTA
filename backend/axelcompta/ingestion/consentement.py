"""Statut du consentement bancaire DSP2 (doc 14 §2.2).

Pur : aucune I/O. La date vient de `item.authentication_expires_at`
(doc 16 §3.2). À 14 jours ou moins, le dossier est à renouveler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Protocol

from axelcompta.core.ids import DossierId

DELAI_RENOUVELLEMENT = timedelta(days=14)
_SENTINELLE = "0000-00-00"


class StatutConsentement(Enum):
    JAMAIS_CONNECTE = "jamais_connecte"
    EXPIRE = "expire"
    A_RENOUVELER = "a_renouveler"
    ACTIF = "actif"


class SanteConnexion(Enum):
    """État de la connexion bancaire, distinct de l'expiration du consentement.

    `auth_requise` (SCA à refaire) prime sur un compte en pause ou sans accès :
    c'est une connexion cassée, pas un chauffeur simplement inactif (doc 16 §5).
    """

    JAMAIS_CONNECTE = "jamais_connecte"
    AUTH_REQUISE = "auth_requise"
    SANS_ACCES = "sans_acces"
    EN_PAUSE = "en_pause"
    OK = "ok"


def classer(expire_le: date | None, aujourd_hui: date) -> StatutConsentement:
    if expire_le is None:
        return StatutConsentement.JAMAIS_CONNECTE
    if expire_le < aujourd_hui:
        return StatutConsentement.EXPIRE
    if expire_le <= aujourd_hui + DELAI_RENOUVELLEMENT:
        return StatutConsentement.A_RENOUVELER
    return StatutConsentement.ACTIF


def _date_expiration(valeur: object) -> date | None:
    if not isinstance(valeur, str) or valeur.startswith(_SENTINELLE):
        return None
    try:
        return datetime.strptime(valeur[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _comptes(payload: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(payload, list):
        return payload
    return [compte for compte in payload.values() if isinstance(compte, dict)]


def expiration_la_plus_proche(payload: dict[str, Any] | list[Any]) -> date | None:
    """La date la plus tôt parmi les comptes connectés, ou None si aucun."""
    dates = [
        trouvee
        for compte in _comptes(payload)
        if isinstance(compte, dict)
        for trouvee in (_date_expiration(_item(compte).get("authentication_expires_at")),)
        if trouvee is not None
    ]
    return min(dates) if dates else None


def _item(compte: dict[str, Any]) -> dict[str, Any]:
    item = compte.get("item")
    return item if isinstance(item, dict) else {}


def _vrai(valeur: object) -> bool:
    return valeur is True or valeur == 1 or valeur == "true"


def _faux(valeur: object) -> bool:
    return valeur is False or valeur == 0 or valeur == "false"


@dataclass(frozen=True, slots=True)
class ReleveSante:
    statut: SanteConnexion
    en_pause: bool
    acces_donnees: bool
    dernier_rafraichissement: datetime | None


def relever_sante(payload: dict[str, Any] | list[Any]) -> ReleveSante:
    """Le plus mauvais compte du contact. Pas d'IBAN, pas de nom."""
    comptes = [compte for compte in _comptes(payload) if isinstance(compte, dict)]
    if not comptes:
        return ReleveSante(SanteConnexion.JAMAIS_CONNECTE, False, False, None)
    en_pause = any(
        _vrai(compte.get("paused")) or _vrai(_item(compte).get("paused")) for compte in comptes
    )
    acces = not any(_faux(compte.get("data_access")) for compte in comptes)
    auth_requise = any(
        _item(compte).get("status_code_info") == "sca_required_webview" for compte in comptes
    )
    if auth_requise:
        statut = SanteConnexion.AUTH_REQUISE
    elif not acces:
        statut = SanteConnexion.SANS_ACCES
    elif en_pause:
        statut = SanteConnexion.EN_PAUSE
    else:
        statut = SanteConnexion.OK
    rafraichissements = []
    for compte in comptes:
        trouve = _horodatage_rafraichissement(_item(compte).get("last_successful_refresh"))
        if trouve is not None:
            rafraichissements.append(trouve)
    return ReleveSante(
        statut,
        en_pause,
        acces,
        min(rafraichissements) if rafraichissements else None,
    )


def _horodatage_rafraichissement(valeur: object) -> datetime | None:
    if not isinstance(valeur, str) or valeur.startswith(_SENTINELLE):
        return None
    try:
        return datetime.strptime(valeur, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class ReleveConsentement:
    """Ce que la dernière synchro a relevé pour un dossier. Le statut n'est
    pas stocké ici : il se recalcule à la lecture (`classer`), sinon il
    vieillirait entre deux synchros."""

    dossier_id: DossierId
    expire_le: date | None
    sante: SanteConnexion
    dernier_rafraichissement: datetime | None
    releve_le: datetime

    def statut(self, aujourd_hui: date) -> StatutConsentement:
        return classer(self.expire_le, aujourd_hui)


class ConsentementRepository(Protocol):
    """Relevé du consentement bancaire, une ligne par dossier (Postgres :
    `consentement_postgres.PostgresConsentementRepository`)."""

    def enregistrer(
        self,
        dossier_id: DossierId,
        expire_le: date | None,
        statut: StatutConsentement,
        releve_le: datetime,
        sante: ReleveSante,
    ) -> None: ...
