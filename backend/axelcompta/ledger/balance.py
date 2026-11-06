"""Invariant I7 (doc 06 §1) : la balance s'équilibre à tout instant.

Chaque écriture est vérifiée à l'insertion (I1) ; ce contrôle, quotidien,
vérifie ce que la base contient vraiment : pour chaque dossier, débits =
crédits, journal par journal et au total. Un écart ne se corrige pas
automatiquement : il s'alerte (AXE-807).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from axelcompta.core.ids import DossierId


@dataclass(frozen=True, slots=True)
class SoldeJournal:
    dossier_id: DossierId
    journal: str
    debit_cts: int
    credit_cts: int


@dataclass(frozen=True, slots=True)
class Ecart:
    dossier_id: DossierId
    journal: str | None  # None : le total du dossier
    debit_cts: int
    credit_cts: int

    @property
    def message(self) -> str:
        portee = f"journal {self.journal}" if self.journal else "total"
        return (
            f"balance déséquilibrée : {self.dossier_id}, {portee}, "
            f"débit {self.debit_cts} ≠ crédit {self.credit_cts} (centimes)"
        )


def ecarts(soldes: Iterable[SoldeJournal]) -> list[Ecart]:
    """Les journaux déséquilibrés, puis les dossiers dont le total l'est."""
    resultat: list[Ecart] = []
    totaux: dict[DossierId, tuple[int, int]] = {}
    for solde in soldes:
        if solde.debit_cts != solde.credit_cts:
            resultat.append(
                Ecart(solde.dossier_id, solde.journal, solde.debit_cts, solde.credit_cts)
            )
        debit, credit = totaux.get(solde.dossier_id, (0, 0))
        totaux[solde.dossier_id] = (debit + solde.debit_cts, credit + solde.credit_cts)
    resultat.extend(
        Ecart(dossier_id, None, debit, credit)
        for dossier_id, (debit, credit) in sorted(totaux.items())
        if debit != credit
    )
    return resultat
