"""Une demande d'échange et sa validation (AXE-949).

Le domaine est pur : le temps et l'identifiant sont des paramètres. La
validation dit la première erreur, en français, avec les mots du formulaire :
le front la montre telle quelle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

from axelcompta.core.errors import DomaineError, SaisieInvalide

Role = Literal["cabinet", "centrale"]
ROLES: tuple[str, ...] = get_args(Role)

LONGUEUR_MAX = {"nom": 100, "email": 254, "organisation": 150, "message": 2000}
LIBELLES = {"nom": "nom", "email": "e-mail", "organisation": "organisation", "message": "message"}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Les retours à la ligne et les tabulations restent permis dans le message.
_CONTROLES = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TropDeDemandes(DomaineError):
    """Trop de demandes reçues sur la dernière heure : on demande de patienter."""


@dataclass(frozen=True, slots=True)
class DemandeEchange:
    id: str
    nom: str
    email: str
    organisation: str
    role: Role
    message: str | None
    cree_le: datetime
    notifiee_le: datetime | None = None
    tentatives: int = 0
    derniere_erreur: str | None = None


def _nettoyer(valeur: str | None) -> str:
    return _CONTROLES.sub("", valeur or "").strip()


def _verifier_longueur(champ: str, valeur: str) -> None:
    if len(valeur) > LONGUEUR_MAX[champ]:
        raise SaisieInvalide(
            f"Le champ « {LIBELLES[champ]} » est trop long "
            f"({LONGUEUR_MAX[champ]} caractères au plus)."
        )


def preparer_demande(
    *,
    id: str,  # noqa: A002 — le nom de la colonne
    nom: str,
    email: str,
    organisation: str,
    role: str,
    message: str | None,
    cree_le: datetime,
) -> DemandeEchange:
    """Nettoie et vérifie la saisie. Lève `SaisieInvalide` à la première erreur."""
    nom_net = _nettoyer(nom)
    email_net = _nettoyer(email).lower()
    organisation_net = _nettoyer(organisation)
    message_net = _nettoyer(message) or None

    if not nom_net:
        raise SaisieInvalide("Indiquez votre nom.")
    if not _EMAIL.match(email_net):
        raise SaisieInvalide("Indiquez une adresse e-mail valide.")
    if not organisation_net:
        raise SaisieInvalide("Indiquez votre organisation.")
    if role not in ROLES:
        raise SaisieInvalide("Indiquez si vous êtes un cabinet ou une centrale.")
    for champ, valeur in (
        ("nom", nom_net),
        ("email", email_net),
        ("organisation", organisation_net),
        ("message", message_net or ""),
    ):
        _verifier_longueur(champ, valeur)

    return DemandeEchange(
        id=id,
        nom=nom_net,
        email=email_net,
        organisation=organisation_net,
        role="cabinet" if role == "cabinet" else "centrale",
        message=message_net,
        cree_le=cree_le,
    )
