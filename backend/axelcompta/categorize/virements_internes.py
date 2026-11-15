"""Virements entre deux comptes bancaires du même dossier (AXE-826).

Les banques « à enveloppes » (MK DRIVING : compte PRO, Social, Fiscal,
Prélèvements à venir) déplacent l'argent entre sous-comptes par virements
libellés « carburant », « cotisation URSSAF »… Lus seuls, ces libellés
passent pour des dépenses. Vus ensemble, ce sont deux jambes d'un même
mouvement : une sortie sur un compte, la même entrée sur un autre.

Appariement : montant opposé au centime, dates à un jour près, et :

* deux comptes bancaires connus et différents ;
* ou le **même libellé** (AXE-930) : certaines banques à enveloppes montrent
  les deux jambes sur le même compte (« cotisation URSSAF » −50 € / +50 €,
  le même jour). Une sortie et son remboursement du même libellé tombent
  aussi ici : ensemble, ils ne sont ni un gain ni une charge.

Chaque opération sert au plus une fois ; on apparie d'abord les jambes les
plus proches dans le temps, puis celles qui portent le même libellé. Pur,
sans I/O.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from axelcompta.core.ids import TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction

ECART_MAX_JOURS = 1
CATEGORIE_VIREMENT_INTERNE = "virement_interne"


@dataclass(frozen=True, slots=True)
class Jambe:
    """Une opération bancaire vue pour l'appariement : la transaction à la
    synchro, l'écriture bancaire pour la reprise (AXE-930)."""

    id: str
    date: date
    montant_cts: int
    compte_bancaire: str | None
    libelle: str


def apparier_virements_internes(
    transactions: Sequence[NormalizedTransaction],
) -> dict[TransactionId, TransactionId]:
    """`{id: id de l'autre jambe}`, dans les deux sens."""
    jambes = [
        Jambe(str(t.id), t.date, t.montant_cts, t.compte_bancaire, t.libelle) for t in transactions
    ]
    return {TransactionId(a): TransactionId(b) for a, b in apparier(jambes).items()}


def apparier(jambes: Sequence[Jambe]) -> dict[str, str]:
    """`{id: id de l'autre jambe}`, dans les deux sens."""
    par_montant: dict[int, list[Jambe]] = defaultdict(list)
    for jambe in jambes:
        if jambe.montant_cts != 0:
            par_montant[jambe.montant_cts].append(jambe)
    paires: dict[str, str] = {}
    for montant, sorties in sorted(par_montant.items()):
        if montant >= 0:
            continue
        entrees = par_montant.get(-montant, [])
        for sortie, entree in _meilleures_paires(sorties, entrees):
            paires[sortie.id] = entree.id
            paires[entree.id] = sortie.id
    return paires


def _libelle(jambe: Jambe) -> str:
    return " ".join(jambe.libelle.lower().split())


def _comptes_distincts(sortie: Jambe, entree: Jambe) -> bool:
    return (
        sortie.compte_bancaire is not None
        and entree.compte_bancaire is not None
        and sortie.compte_bancaire != entree.compte_bancaire
    )


def _possible(sortie: Jambe, entree: Jambe) -> bool:
    if abs((sortie.date - entree.date).days) > ECART_MAX_JOURS:
        return False
    return _comptes_distincts(sortie, entree) or _libelle(sortie) == _libelle(entree)


def _meilleures_paires(sorties: list[Jambe], entrees: list[Jambe]) -> list[tuple[Jambe, Jambe]]:
    candidates = [
        (abs((s.date - e.date).days), _libelle(s) != _libelle(e), s, e)
        for s in sorties
        for e in entrees
        if _possible(s, e)
    ]
    candidates.sort(key=lambda c: (c[0], c[1], c[2].id, c[3].id))
    prises: set[str] = set()
    retenues: list[tuple[Jambe, Jambe]] = []
    for _ecart, _libelle_different, sortie, entree in candidates:
        if sortie.id in prises or entree.id in prises:
            continue
        prises.update((sortie.id, entree.id))
        retenues.append((sortie, entree))
    return retenues
