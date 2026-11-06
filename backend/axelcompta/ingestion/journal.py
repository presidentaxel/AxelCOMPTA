"""Journal d'ingestion : archive brute, quarantaine, curseur (doc 12 §1.2,
doc 16 §9 point 2). Frontière de persistance, comme `DossierRepository`."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from axelcompta.core.ids import DossierId


@dataclass(frozen=True, slots=True)
class EntreeQuarantaine:
    dossier_id: DossierId
    source: str
    motif: str
    transaction_id: str | None
    payload: dict[str, object]
    # Empreinte stable (dossier, source, motif, contenu) : la même entrée
    # n'est jamais mise deux fois en quarantaine (AXE-424 : on la résout par lui).
    id: str = ""


def empreinte(*parties: str, payload: dict[str, object]) -> str:
    """Identifiant déterministe d'une entrée : sha256 du contexte et du
    payload canonique (clés triées). Deux lectures du même contenu donnent la
    même empreinte, ce qui rend l'archivage et la quarantaine idempotents."""
    canonique = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256("|".join((*parties, canonique)).encode()).hexdigest()


def maintenant() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class JournalIngestion(ABC):
    @abstractmethod
    def archiver(
        self,
        dossier_id: DossierId,
        source: str,
        transaction_id: str | None,
        updated_at: str | None,
        payload: dict[str, object],
    ) -> None:
        """Idempotent : archiver deux fois le même contenu n'écrit qu'une fois."""

    @abstractmethod
    def mettre_en_quarantaine(
        self,
        dossier_id: DossierId,
        source: str,
        motif: str,
        transaction_id: str | None,
        payload: dict[str, object],
    ) -> None:
        """Idempotent sur (dossier, source, motif, contenu)."""

    @abstractmethod
    def lister_quarantaine(self, dossier_id: DossierId) -> tuple[EntreeQuarantaine, ...]: ...

    @abstractmethod
    def curseur(self, dossier_id: DossierId, source: str) -> datetime | None:
        """`None` : jamais synchronisé, la prochaine lecture est complète."""

    @abstractmethod
    def avancer_curseur(self, dossier_id: DossierId, source: str, valeur: datetime) -> None:
        """Ne recule jamais : une valeur antérieure au curseur courant est ignorée."""

    @abstractmethod
    def comptes_des_transactions(self, dossier_id: DossierId, source: str) -> dict[str, str]:
        """`{transaction_id: account_id}` lu dans l'archive brute (AXE-832).
        Une transaction sans `account_id` est absente du résultat."""


def compte_du_payload(payload: dict[str, object]) -> str | None:
    """`account_id` d'une ligne archivée, ou `None`."""
    valeur = payload.get("account_id")
    texte = "" if valeur is None else str(valeur).strip()
    return texte or None


class InMemoryJournalIngestion(JournalIngestion):
    def __init__(self) -> None:
        self.brut: dict[str, dict[str, object]] = {}
        self._comptes: dict[tuple[str, str, str], str] = {}
        self._quarantaine: dict[str, EntreeQuarantaine] = {}
        self._curseurs: dict[tuple[str, str], datetime] = {}

    def archiver(
        self,
        dossier_id: DossierId,
        source: str,
        transaction_id: str | None,
        updated_at: str | None,
        payload: dict[str, object],
    ) -> None:
        self.brut.setdefault(empreinte(dossier_id, source, payload=payload), payload)
        compte = compte_du_payload(payload)
        if transaction_id is not None and compte is not None:
            self._comptes[(dossier_id, source, transaction_id)] = compte

    def mettre_en_quarantaine(
        self,
        dossier_id: DossierId,
        source: str,
        motif: str,
        transaction_id: str | None,
        payload: dict[str, object],
    ) -> None:
        cle = empreinte(dossier_id, source, motif, payload=payload)
        self._quarantaine.setdefault(
            cle, EntreeQuarantaine(dossier_id, source, motif, transaction_id, payload, cle)
        )

    def lister_quarantaine(self, dossier_id: DossierId) -> tuple[EntreeQuarantaine, ...]:
        return tuple(e for e in self._quarantaine.values() if e.dossier_id == dossier_id)

    def curseur(self, dossier_id: DossierId, source: str) -> datetime | None:
        return self._curseurs.get((dossier_id, source))

    def avancer_curseur(self, dossier_id: DossierId, source: str, valeur: datetime) -> None:
        actuel = self._curseurs.get((dossier_id, source))
        if actuel is None or valeur > actuel:
            self._curseurs[(dossier_id, source)] = valeur

    def comptes_des_transactions(self, dossier_id: DossierId, source: str) -> dict[str, str]:
        return {
            transaction_id: compte
            for (dossier, src, transaction_id), compte in self._comptes.items()
            if dossier == dossier_id and src == source
        }
