"""Implémentation en mémoire de LedgerService — pour la démo semaine 0 (doc 17) :
prouve la couture réconciliation → écriture → clôture sans dépendre de
Postgres. `repository.py` fournit l'implémentation Postgres réelle.
"""

from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId

from .invariants import verifier_equilibre
from .models import Ecriture
from .periodes import Periode, verifier_hors_periode_close
from .service import LedgerService


class InMemoryLedgerService(LedgerService):
    def __init__(self) -> None:
        self._par_dossier: dict[DossierId, list[Ecriture]] = {}
        self._closes: dict[DossierId, list[Periode]] = {}

    def enregistrer(self, ecriture: Ecriture) -> EcritureId:
        verifier_equilibre(ecriture)
        verifier_hors_periode_close(ecriture.date, self.periodes_closes(ecriture.dossier_id))
        self._par_dossier.setdefault(ecriture.dossier_id, []).append(ecriture)
        return ecriture.id

    def periodes_closes(self, dossier_id: DossierId) -> tuple[Periode, ...]:
        return tuple(self._closes.get(dossier_id, ()))

    def clore(self, dossier_id: DossierId, debut: date, fin: date) -> None:
        """Ce que fait la ligne `exercices_clos` en base (tests, démo)."""
        self._closes.setdefault(dossier_id, []).append((debut, fin))

    def grand_livre(self, dossier_id: DossierId) -> tuple[Ecriture, ...]:
        return tuple(sorted(self._par_dossier.get(dossier_id, []), key=lambda e: e.date))
