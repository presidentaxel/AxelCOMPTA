"""Ce qui attend encore au compte d'attente sur l'exercice (AXE-1013). Pur.

Sous le CA, les charges et le résultat d'Entreprises : les entrées (471 au
crédit) et les sorties (471 au débit) pas encore classées. Sur le grand
livre vu par les écrans, où les décisions sont déjà repliées. Ne comptent
pas : les paires annulées, ni un virement de plateforme soldé par sa
semaine Rollee (ni l'écriture qui le solde).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from axelcompta.ingestion.ecritures_semaines import id_solde
from axelcompta.ledger.contrepassation import annulees
from axelcompta.ledger.models import Ecriture, Sens

from .revue import COMPTE_ATTENTE


def non_classes(ecritures: Sequence[Ecriture], debut: date, fin: date) -> tuple[int, int]:
    """(entrées, sorties) en centimes, positives."""
    ids = {e.id for e in ecritures}
    soldes = {id_solde(str(e.id)) for e in ecritures}
    exclues = annulees(ecritures)
    entrees = sorties = 0
    for e in ecritures:
        # shortcut: un virement soldé compte comme classé en entier, même si
        # sa semaine ne l'a soldé qu'en partie ; à affiner si l'écart se voit.
        if e.id in exclues or e.id in soldes or id_solde(str(e.id)) in ids:
            continue
        if not debut <= e.date <= fin:
            continue
        for ligne in e.lignes:
            if ligne.compte.startswith(COMPTE_ATTENTE):
                if ligne.sens is Sens.CREDIT:
                    entrees += ligne.montant.centimes
                else:
                    sorties += ligne.montant.centimes
    return entrees, sorties
