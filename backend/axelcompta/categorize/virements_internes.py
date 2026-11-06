"""Virements entre deux comptes bancaires du même dossier (AXE-826).

Les banques « à enveloppes » (MK DRIVING : compte PRO, Social, Fiscal,
Prélèvements à venir) déplacent l'argent entre sous-comptes par virements
libellés « carburant », « cotisation URSSAF »… Lus seuls, ces libellés
passent pour des dépenses. Vus ensemble, ce sont deux jambes d'un même
mouvement : une sortie sur un compte, la même entrée sur un autre.

Appariement : montant opposé au centime, dates à un jour près, deux comptes
bancaires connus et différents. Chaque opération sert au plus une fois ; on
apparie d'abord les jambes les plus proches dans le temps, puis celles qui
portent le même libellé. Pur, sans I/O.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from axelcompta.core.ids import TransactionId
from axelcompta.ingestion.providers.base import NormalizedTransaction

ECART_MAX_JOURS = 1
CATEGORIE_VIREMENT_INTERNE = "virement_interne"


def apparier_virements_internes(
    transactions: Sequence[NormalizedTransaction],
) -> dict[TransactionId, TransactionId]:
    """`{id: id de l'autre jambe}`, dans les deux sens. Une opération sans
    compte bancaire connu n'est jamais appariée : on ne saurait pas dire
    qu'elle va d'un compte du dossier à un autre."""
    par_montant: dict[int, list[NormalizedTransaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.compte_bancaire is not None and transaction.montant_cts != 0:
            par_montant[transaction.montant_cts].append(transaction)
    paires: dict[TransactionId, TransactionId] = {}
    for montant, sorties in sorted(par_montant.items()):
        if montant >= 0:
            continue
        entrees = par_montant.get(-montant, [])
        for sortie, entree in _meilleures_paires(sorties, entrees):
            paires[sortie.id] = entree.id
            paires[entree.id] = sortie.id
    return paires


def _meilleures_paires(
    sorties: list[NormalizedTransaction], entrees: list[NormalizedTransaction]
) -> list[tuple[NormalizedTransaction, NormalizedTransaction]]:
    candidates = [
        (abs((s.date - e.date).days), s.libelle.strip().lower() != e.libelle.strip().lower(), s, e)
        for s in sorties
        for e in entrees
        if s.compte_bancaire != e.compte_bancaire and abs((s.date - e.date).days) <= ECART_MAX_JOURS
    ]
    candidates.sort(key=lambda c: (c[0], c[1], str(c[2].id), str(c[3].id)))
    prises: set[TransactionId] = set()
    retenues: list[tuple[NormalizedTransaction, NormalizedTransaction]] = []
    for _ecart, _libelle_different, sortie, entree in candidates:
        if sortie.id in prises or entree.id in prises:
            continue
        prises.update((sortie.id, entree.id))
        retenues.append((sortie, entree))
    return retenues
