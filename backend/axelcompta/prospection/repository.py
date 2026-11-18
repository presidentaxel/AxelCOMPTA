"""Où les demandes d'échange sont gardées : un contrat, et sa version en mémoire."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from axelcompta.prospection.models import DemandeEchange


class DemandesRepository(Protocol):
    def ajouter(self, demande: DemandeEchange) -> None: ...

    def email_recu_depuis(self, email: str, depuis: datetime) -> bool:
        """Vrai si cette adresse a déjà une demande reçue à partir de `depuis`."""
        ...

    def nombre_depuis(self, depuis: datetime) -> int: ...

    def non_notifiees(
        self, avant: datetime, tentatives_max: int, limite: int
    ) -> list[DemandeEchange]:
        """Les demandes reçues avant `avant`, pas encore notifiées, sous le plafond d'essais."""
        ...

    def marquer_notifiee(self, id: str, le: datetime) -> None: ...  # noqa: A002

    def noter_echec(self, id: str, raison: str) -> None: ...  # noqa: A002


class DemandesMemoire:
    def __init__(self) -> None:
        self.demandes: dict[str, DemandeEchange] = {}

    def ajouter(self, demande: DemandeEchange) -> None:
        self.demandes[demande.id] = demande

    def email_recu_depuis(self, email: str, depuis: datetime) -> bool:
        return any(d.email == email and d.cree_le >= depuis for d in self.demandes.values())

    def nombre_depuis(self, depuis: datetime) -> int:
        return sum(1 for d in self.demandes.values() if d.cree_le >= depuis)

    def non_notifiees(
        self, avant: datetime, tentatives_max: int, limite: int
    ) -> list[DemandeEchange]:
        trouvees = [
            d
            for d in self.demandes.values()
            if d.notifiee_le is None and d.tentatives < tentatives_max and d.cree_le < avant
        ]
        return sorted(trouvees, key=lambda d: d.cree_le)[:limite]

    def marquer_notifiee(self, id: str, le: datetime) -> None:  # noqa: A002
        self.demandes[id] = replace(self.demandes[id], notifiee_le=le)

    def noter_echec(self, id: str, raison: str) -> None:  # noqa: A002
        actuelle = self.demandes[id]
        self.demandes[id] = replace(
            actuelle, tentatives=actuelle.tentatives + 1, derniere_erreur=raison
        )
