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

from axelcompta.core.errors import Conflit

# (début, fin) inclus, d'un exercice clos.
Periode = tuple[date, date]


class PeriodeClose(Conflit):
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


def date_de_report(
    jour: date, periodes: Sequence[Periode], debut_ouvert: date | None = None
) -> date:
    """`jour` s'il est ouvert. Sinon, le premier jour de l'exercice ouvert :
    `debut_ouvert` (le début d'exercice du dossier) quand il vient après les
    exercices clos qui couvrent `jour`, sinon le lendemain de leur fin
    (AXE-838 : premier exercice long, date de clôture changée, trou)."""
    if periode_close_de(jour, periodes) is None:
        return jour
    lendemain = jour
    while (periode := periode_close_de(lendemain, periodes)) is not None:
        lendemain = periode[1] + timedelta(days=1)
    if debut_ouvert is not None and debut_ouvert > lendemain:
        return debut_ouvert
    return lendemain
