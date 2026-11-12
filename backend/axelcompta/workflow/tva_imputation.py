"""Les lignes d'une imputation, TVA déductible séparée (AXE-831).

Une dépense de 60,00 € TTC en carburant ne va plus tout entière en 6061 :
50,00 € en 6061 et 10,00 € en 44566. Le total reste égal au montant bancaire
au centime. Les deux lignes portent le code de la règle (« estimée ») : un
justificatif pourra la remplacer.
"""

from __future__ import annotations

from axelcompta.core.money import Money
from axelcompta.ledger.models import LigneEcriture, Sens
from axelcompta.packs.tva_deductible import RegleTva, tva_recuperable


def lignes_imputees(
    compte: str, sens: Sens, montant: Money, regle: RegleTva | None
) -> tuple[LigneEcriture, ...]:
    """Le compte d'abord (les écrans lisent la première ligne), puis la TVA.
    Une seule ligne quand rien ne se récupère."""
    recuperable = tva_recuperable(montant.centimes, regle) if regle is not None else 0
    if regle is None or recuperable == 0:
        return (LigneEcriture(compte=compte, sens=sens, montant=montant),)
    charge = Money(montant.centimes - recuperable, montant.devise)
    tva = Money(recuperable, montant.devise)
    return (
        LigneEcriture(compte=compte, sens=sens, montant=charge, code_tva=regle.code),
        LigneEcriture(compte=regle.compte, sens=sens, montant=tva, code_tva=regle.code),
    )
