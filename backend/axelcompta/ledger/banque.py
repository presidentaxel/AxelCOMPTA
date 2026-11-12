"""Lecture des lignes de banque d'une écriture (AXE-832).

Depuis qu'un dossier a un sous-compte de banque par compte bancaire (5121,
5122…), « la ligne 512 » d'une écriture se reconnaît par
`core.pcg.est_compte_banque`, jamais par une égalité avec `"512"`.
"""

from __future__ import annotations

from axelcompta.core.pcg import est_compte_banque, est_compte_tva_deductible

from .models import Ecriture, LigneEcriture, Sens


def ligne_banque(ecriture: Ecriture) -> LigneEcriture | None:
    """Première ligne de banque de l'écriture, ou `None` (OD sans banque)."""
    return next((ligne for ligne in ecriture.lignes if est_compte_banque(ligne.compte)), None)


def montant_bancaire(ecriture: Ecriture) -> int:
    """Montant signé façon relevé (positif = argent reçu), lu sur la ligne de
    banque ; 0 pour une écriture sans banque."""
    ligne = ligne_banque(ecriture)
    if ligne is None:
        return 0
    signe = 1 if ligne.sens is Sens.DEBIT else -1
    return signe * ligne.montant.centimes


def comptes_hors_banque(ecriture: Ecriture) -> list[str]:
    """Les contreparties de la banque, dans l'ordre des lignes, sans la TVA
    déductible (4456x) : une dépense de carburant reste « en 6061 » même
    quand sa TVA est séparée (AXE-831)."""
    return [
        ligne.compte
        for ligne in ecriture.lignes
        if not est_compte_banque(ligne.compte) and not est_compte_tva_deductible(ligne.compte)
    ]


def est_reclassement_bancaire(ecriture: Ecriture) -> bool:
    """Écriture qui ne fait que déplacer de l'argent entre comptes de banque
    du dossier (ventilation 512 → 512x, virement interne 512x → 512y). Ce
    n'est pas une opération du relevé : elle ne s'affiche pas au chauffeur."""
    return bool(ecriture.lignes) and all(
        est_compte_banque(ligne.compte) for ligne in ecriture.lignes
    )
