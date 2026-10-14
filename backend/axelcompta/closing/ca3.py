"""CA3 pré-remplie depuis les comptes de TVA, avant leur liquidation.

Le réel normal (déclaration 3310-CA3) est la trajectoire TVA de la V1
(doc 02 §7bis, doc 06 §6). Ici le pivot, pas le PDF : trois montants en
centimes, ceux qui cadrent la liquidation déjà passée en écriture d'OD.
"""

from __future__ import annotations

from .liasse_2033 import Balance


def declaration_ca3(balance: Balance) -> dict[str, int]:
    """`DUE` positif = TVA à décaisser. Négatif = crédit à reporter."""
    collectee = -sum(solde for compte, solde in balance.items() if compte.startswith("4457"))
    deductible = sum(solde for compte, solde in balance.items() if compte.startswith("4456"))
    return {"COLLECTEE": collectee, "DEDUCTIBLE": deductible, "DUE": collectee - deductible}
