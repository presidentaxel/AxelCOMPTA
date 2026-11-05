"""Contre-passation d'une écriture déjà validée (doc 06 §1).

L'originale n'est jamais modifiée. L'inverse a les mêmes comptes et les
mêmes montants, le sens opposé, un identifiant stable pour rester
idempotente.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from axelcompta.core.ids import EcritureId

from .models import Ecriture, Journal, LigneEcriture, Sens
from .periodes import Periode, date_de_report

SUFFIXE = ":contrepassation"


def _sens_oppose(sens: Sens) -> Sens:
    return Sens.CREDIT if sens is Sens.DEBIT else Sens.DEBIT


def contrepasser(ecriture: Ecriture, periodes_closes: Sequence[Periode] = ()) -> Ecriture:
    """Datée comme l'originale, ou au premier jour de l'exercice ouvert si
    l'originale tombe dans un exercice clos (I4)."""
    le: date = date_de_report(ecriture.date, periodes_closes)
    return Ecriture(
        id=id_contrepassation(ecriture.id),
        dossier_id=ecriture.dossier_id,
        journal=Journal.OD,
        date=le,
        libelle=f"Contre-passation {ecriture.libelle}",
        reference_piece=str(ecriture.id),
        lignes=tuple(
            LigneEcriture(
                compte=ligne.compte,
                sens=_sens_oppose(ligne.sens),
                montant=ligne.montant,
                analytique=ligne.analytique,
                code_tva=ligne.code_tva,
            )
            for ligne in ecriture.lignes
        ),
    )


def id_contrepassation(ecriture_id: EcritureId) -> EcritureId:
    return EcritureId(f"{ecriture_id}{SUFFIXE}")


def origine(ecriture_id: EcritureId) -> EcritureId | None:
    """Id de l'écriture annulée si `ecriture_id` est une contre-passation."""
    if ecriture_id.endswith(SUFFIXE):
        return EcritureId(ecriture_id.removesuffix(SUFFIXE))
    return None


def annulees(ecritures: Iterable[Ecriture]) -> frozenset[EcritureId]:
    """Les originales contre-passées et leurs inverses. La paire se neutralise :
    rien à trancher, ni pour l'une ni pour l'autre."""
    ids: set[EcritureId] = set()
    for ecriture in ecritures:
        source = origine(ecriture.id)
        if source is not None:
            ids.update((ecriture.id, source))
    return frozenset(ids)
