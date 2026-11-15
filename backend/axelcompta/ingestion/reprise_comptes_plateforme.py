"""Reprendre sur les comptes de l'expert les semaines de plateforme déjà écrites (AXE-931). Pur.

Avant AXE-931, une semaine soldée s'écrivait sur un seul 467, les espèces
au compte de l'associé (455, 108 en EI), le hors course en 7068 et la
commission en 622. Le schéma de l'expert-comptable veut un 467 par
plateforme, la caisse (530), le 708 et le 6222.

Une OD écrite ne change pas : une OD `{S}:comptes-plateforme` déplace chaque
montant de l'ancien compte vers le nouveau. Elle garde la pièce de la
semaine, et son suffixe la fait contre-passer avec la semaine si le lien
Rollee est retiré.
"""

from __future__ import annotations

from collections.abc import Sequence

from axelcompta.core.ids import EcritureId
from axelcompta.ingestion.ecritures_semaines import (
    COMPTE_ESPECES,
    COMPTE_HORS_COURSE,
    SUFFIXE_FRAIS,
    SUFFIXE_RECETTE,
    SUFFIXE_SOLDE,
    compte_creance,
)
from axelcompta.ingestion.ecritures_settlement import COMPTE_COMMISSION
from axelcompta.ledger.contrepassation import annulees, origine
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.periodes import Periode, date_de_report

SUFFIXE_REPRISE = ":comptes-plateforme"
REPRISES = {"467": None, "7068": COMPTE_HORS_COURSE, "622": COMPTE_COMMISSION}
# Le compte de l'associé n'apparaît dans une recette que pour les espèces.
COMPTES_ASSOCIE = ("455", "108")


def id_reprise(source_id: EcritureId) -> EcritureId:
    return EcritureId(f"{source_id}{SUFFIXE_REPRISE}")


def _plateforme(ecriture: Ecriture) -> str:
    """« uber:2026-11-02 » → « uber »."""
    return (ecriture.reference_piece or "").split(":", 1)[0]


def _cible(ligne: LigneEcriture, ecriture: Ecriture) -> str | None:
    """Le nouveau compte d'une ligne, `None` si elle ne bouge pas."""
    if ligne.compte in REPRISES:
        cible = REPRISES[ligne.compte] or compte_creance(_plateforme(ecriture))
        return cible if cible != ligne.compte else None
    if ecriture.id.endswith(SUFFIXE_RECETTE) and ligne.sens is Sens.DEBIT:
        if ligne.compte.startswith(COMPTES_ASSOCIE):
            return COMPTE_ESPECES
    return None


def ecriture_reprise(
    ecriture: Ecriture, periodes_closes: Sequence[Periode] = ()
) -> Ecriture | None:
    """L'OD qui amène une OD de semaine sur les comptes de l'expert ; `None`
    si elle y est déjà."""
    lignes: list[LigneEcriture] = []
    for ligne in ecriture.lignes:
        cible = _cible(ligne, ecriture)
        if cible is None or not ligne.montant.centimes:
            continue
        inverse = Sens.CREDIT if ligne.sens is Sens.DEBIT else Sens.DEBIT
        lignes.append(LigneEcriture(cible, ligne.sens, ligne.montant))
        lignes.append(LigneEcriture(ligne.compte, inverse, ligne.montant))
    if not lignes:
        return None
    return Ecriture(
        id=id_reprise(ecriture.id),
        dossier_id=ecriture.dossier_id,
        journal=Journal.OD,
        date=date_de_report(ecriture.date, periodes_closes),
        libelle=f"Comptes de l'expert : {ecriture.libelle}"[:200],
        reference_piece=ecriture.reference_piece,
        lignes=tuple(lignes),
    )


def reprises(
    grand_livre: Sequence[Ecriture], periodes_closes: Sequence[Periode] = ()
) -> list[Ecriture]:
    """Les OD de reprise des semaines en vigueur, pas encore reprises."""
    exclues = annulees(grand_livre)
    ids = {e.id for e in grand_livre}
    a_ecrire: list[Ecriture] = []
    for e in grand_livre:
        if (
            e.id in exclues
            or origine(e.id) is not None
            or not e.id.endswith((SUFFIXE_RECETTE, SUFFIXE_SOLDE, SUFFIXE_FRAIS))
            or id_reprise(e.id) in ids
        ):
            continue
        od = ecriture_reprise(e, periodes_closes)
        if od is not None:
            a_ecrire.append(od)
    return a_ecrire
