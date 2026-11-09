"""Exports et consultations d'un dossier, tracés au journal d'audit (AXE-812).

Un téléchargement du FEC, d'une liasse, du grand livre ou de la balance
laisse une ligne `export` : qui, quel fichier, quand. Le dirigeant relit
ces lignes sur son écran Compte (« qui a consulté ou exporté mon dossier »).
Le journal est en ajout seul (trigger `journal_audit_immuable`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.engine import Engine

from axelcompta.core.ids import DossierId, UserId
from axelcompta.core.rls import appliquer_rls

from .audit import ACTE_CONNEXION, ACTE_CONSULTATION, ACTE_EXPORT, noter
from .orm import journal_audit

# Ce que le dirigeant voit de son journal : qui a lu ou emporté ses comptes.
ACTES_VISIBLES_DU_DIRIGEANT = (ACTE_EXPORT, ACTE_CONSULTATION, ACTE_CONNEXION)
LIMITE_LECTURE = 200


@dataclass(frozen=True, slots=True)
class ActeTrace:
    type_acte: str
    reference: str
    acteur: UserId
    le: datetime


class JournalAcces(Protocol):
    def noter(
        self, dossier_id: DossierId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None: ...

    def lister(self, dossier_id: DossierId, types: Iterable[str]) -> list[ActeTrace]:
        """Les plus récents d'abord, `LIMITE_LECTURE` au plus."""
        ...


class PostgresJournalAcces:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def noter(
        self, dossier_id: DossierId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None:
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            noter(connexion, dossier_id, type_acte, reference, acteur, le)

    def lister(self, dossier_id: DossierId, types: Iterable[str]) -> list[ActeTrace]:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            lignes = connexion.execute(
                select(journal_audit)
                .where(
                    journal_audit.c.dossier_id == dossier_id,
                    journal_audit.c.type_acte.in_(list(types)),
                )
                .order_by(journal_audit.c.acte_le.desc())
                .limit(LIMITE_LECTURE)
            ).all()
        return [
            ActeTrace(ligne.type_acte, ligne.reference, UserId(ligne.acteur), ligne.acte_le)
            for ligne in lignes
        ]


@dataclass
class JournalAccesMemoire:
    actes: list[tuple[DossierId, ActeTrace]] = field(default_factory=list)

    def noter(
        self, dossier_id: DossierId, type_acte: str, reference: str, acteur: UserId, le: datetime
    ) -> None:
        self.actes.append((dossier_id, ActeTrace(type_acte, reference, acteur, le)))

    def lister(self, dossier_id: DossierId, types: Iterable[str]) -> list[ActeTrace]:
        voulus = set(types)
        du_dossier = [a for d, a in self.actes if d == dossier_id and a.type_acte in voulus]
        return sorted(du_dossier, key=lambda a: a.le, reverse=True)[:LIMITE_LECTURE]
