"""Invariant I4 (doc 06 §1) : aucune écriture sur une période clôturée.

Une période close est un exercice présent dans `exercices_clos`. Une
écriture datée dedans est refusée (`PeriodeClose`) ; en base, le trigger
`ecritures_hors_periode_close` le refuse aussi, même à la connexion
propriétaire.

Une correction qui concerne un exercice clos (contre-passation, imputation)
est passée au premier jour de l'exercice ouvert (`date_de_report`), en
journal OD, et référence l'écriture d'origine (I6) : la liasse et le FEC déjà
produits ne bougent pas.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from axelcompta.core.errors import DomaineError

# (début, fin) inclus, d'un exercice clos.
Periode = tuple[date, date]


class PeriodeClose(DomaineError):
    """Écriture datée dans un exercice déjà clos."""

    def __init__(self, jour: date, periode: Periode) -> None:
        debut, fin = periode
        super().__init__(
            f"L'exercice du {debut:%d/%m/%Y} au {fin:%d/%m/%Y} est clos : "
            f"aucune écriture ne peut y être datée ({jour:%d/%m/%Y})."
        )
        self.jour = jour
        self.periode = periode


def periode_close_de(jour: date, periodes: Sequence[Periode]) -> Periode | None:
    return next(((d, f) for d, f in periodes if d <= jour <= f), None)


def verifier_hors_periode_close(jour: date, periodes: Sequence[Periode]) -> None:
    periode = periode_close_de(jour, periodes)
    if periode is not None:
        raise PeriodeClose(jour, periode)


def date_de_report(jour: date, periodes: Sequence[Periode]) -> date:
    """`jour` s'il est ouvert ; sinon le lendemain de la fin des exercices
    clos qui le couvrent (premier jour de l'exercice ouvert)."""
    periode = periode_close_de(jour, periodes)
    while periode is not None:
        jour = periode[1] + timedelta(days=1)
        periode = periode_close_de(jour, periodes)
    return jour
