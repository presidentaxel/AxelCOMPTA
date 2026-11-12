"""Les lignes d'une imputation, TVA déductible séparée (AXE-831).

Une dépense de 60,00 € TTC en carburant ne va plus tout entière en 6061 :
50,00 € en 6061 et 10,00 € en 44566. Le total reste égal au montant bancaire
au centime. Les deux lignes portent le code de la règle (« estimée ») : un
justificatif pourra la remplacer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from axelcompta.core.money import Money
from axelcompta.core.pcg import est_compte_tva_deductible
from axelcompta.ledger.models import LigneEcriture, Sens
from axelcompta.packs.tva_deductible import (
    PREFIXE_ESTIMEE,
    PREFIXE_RELEVEE,
    RegleTva,
    regle_tva,
    tva_recuperable,
)
from axelcompta.packs.vtc_demo import charger_compte_par_categorie

OrigineTva = Literal["estimee", "relevee"]


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


@dataclass(frozen=True, slots=True)
class TvaAffichee:
    """Ce que la ligne montre. `estimee` vient de la table, et reste ce montant
    une fois écrit. `relevee` est le montant lu sur un justificatif : il
    remplace l'estimation à l'écran."""

    centimes: int
    origine: OrigineTva


def tva_affichee(
    lignes: Sequence[LigneEcriture],
    *,
    montant_ttc_cts: int,
    categorie: str | None,
    jour: date,
    regime_tva: str,
) -> TvaAffichee | None:
    """La TVA à montrer. Un montant déjà posé sur la ligne fait foi : on ne
    recalcule pas par-dessus. Sans ligne de TVA, l'estimation vient de la
    table, pour la date de l'opération."""
    relevee = _somme(lignes, PREFIXE_RELEVEE)
    if relevee:
        return TvaAffichee(relevee, "relevee")
    estimee = _somme(lignes, PREFIXE_ESTIMEE)
    if estimee:
        return TvaAffichee(estimee, "estimee")
    portee = _categorie(lignes, categorie)
    if portee is None:
        return None
    regle = regle_tva(portee, jour, regime_tva)
    if regle is None:
        return None
    centimes = tva_recuperable(abs(montant_ttc_cts), regle)
    if centimes <= 0:
        return None
    return TvaAffichee(centimes, "estimee")


def _somme(lignes: Sequence[LigneEcriture], prefixe: str) -> int:
    return sum(
        ligne.montant.centimes
        for ligne in lignes
        if est_compte_tva_deductible(ligne.compte) and (ligne.code_tva or "").startswith(prefixe)
    )


def _categorie(lignes: Sequence[LigneEcriture], categorie: str | None) -> str | None:
    """La catégorie connue, sinon celle de l'unique compte de charge."""
    if categorie:
        return categorie
    comptes = list(
        dict.fromkeys(ligne.compte for ligne in lignes if ligne.compte[:1] in {"6", "2"})
    )
    if len(comptes) != 1:
        return None
    trouvees = [
        nom for nom, compte in charger_compte_par_categorie().items() if compte == comptes[0]
    ]
    return trouvees[0] if len(trouvees) == 1 else None
