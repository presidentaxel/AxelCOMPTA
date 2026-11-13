"""AXE-803 : LOA — premier loyer étalé (486), engagement hors bilan."""

from __future__ import annotations

import dataclasses
from collections import Counter
from datetime import date, timedelta
from typing import Any

import pytest

from axelcompta.closing.loa import (
    ContratInvalide,
    ContratLoa,
    cca,
    charge_premier_loyer,
    echeances,
    ecritures_loa,
    engagement_restant,
    terme,
    valider,
)
from axelcompta.core.ids import DossierId
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Sens

D = DossierId("d1")
# Critère du ticket : 36 mois, premier loyer de 3 000 €, loyers de 450 €.
CONTRAT = ContratLoa(
    "c1", "DIAC", "Renault Austral", date(2026, 4, 1), 36, 450_00, 3_000_00, 9_000_00
)


def _exercice(annee: int) -> tuple[date, date]:
    return date(annee, 1, 1), date(annee, 12, 31)


def test_le_premier_loyer_s_etale_au_centime() -> None:
    # 2026 : 9 mois sur 36 → 750 € ; 2027 et 2028 : 1 000 € ; 2029 : 3 mois → 250 €.
    parts = [charge_premier_loyer(CONTRAT, *_exercice(a)) for a in range(2026, 2030)]
    assert parts == [750_00, 1_000_00, 1_000_00, 250_00]
    assert sum(parts) == CONTRAT.premier_loyer_cts


def test_la_charge_annuelle_est_juste_au_centime() -> None:
    """2027, année pleine : 1 000 € de premier loyer étalé + 12 loyers de 450 €."""
    debut, fin = _exercice(2027)
    loyers = sum(m for jour, m in echeances(CONTRAT)[1:] if debut <= jour <= fin)
    assert loyers + charge_premier_loyer(CONTRAT, debut, fin) == 6_400_00


def test_les_ecritures_suivent_la_cca() -> None:
    (premiere,) = ecritures_loa(D, (CONTRAT,), *_exercice(2026))
    verifier_equilibre(premiere)
    assert [(x.compte, x.sens, x.montant.centimes) for x in premiere.lignes] == [
        ("486", Sens.DEBIT, 2_250_00),
        ("612", Sens.CREDIT, 2_250_00),
    ]
    (suivante,) = ecritures_loa(D, (CONTRAT,), *_exercice(2027))
    assert [(x.compte, x.sens, x.montant.centimes) for x in suivante.lignes] == [
        ("612", Sens.DEBIT, 1_000_00),
        ("486", Sens.CREDIT, 1_000_00),
    ]
    soldes: Counter[str] = Counter()
    for annee in range(2026, 2031):
        for e in ecritures_loa(D, (CONTRAT,), *_exercice(annee)):
            for x in e.lignes:
                soldes[x.compte] += (1 if x.sens is Sens.DEBIT else -1) * x.montant.centimes
    assert soldes["486"] == 0  # la CCA est entièrement consommée au terme


def test_engagement_hors_bilan() -> None:
    assert terme(CONTRAT) == date(2029, 3, 31)
    assert len(echeances(CONTRAT)) == 36
    # Fin 2026 : loyers d'avril 2026 à mars 2029 = 35, dont 8 déjà payés (mai à déc.).
    assert engagement_restant(CONTRAT, date(2026, 12, 31)) == 27 * 450_00 + 9_000_00
    assert engagement_restant(CONTRAT, terme(CONTRAT)) == 0
    assert cca(CONTRAT, CONTRAT.debut - timedelta(days=1)) == 0


def test_la_fin_de_mois_est_bornee() -> None:
    fin_janvier = dataclasses.replace(CONTRAT, debut=date(2026, 1, 31))
    assert echeances(fin_janvier)[1][0] == date(2026, 2, 28)


@pytest.mark.parametrize(
    "champ, valeur",
    [("loueur", " "), ("duree_mois", 3), ("loyer_mensuel_cts", 0), ("prix_levee_cts", -1)],
)
def test_une_fiche_inutilisable_est_refusee(champ: str, valeur: Any) -> None:
    with pytest.raises(ContratInvalide):
        valider(dataclasses.replace(CONTRAT, **{champ: valeur}))
