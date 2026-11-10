"""AXE-805 : CA3 de chaque période, échéance, liquidation."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.closing.ca3 import declaration_ca3
from axelcompta.closing.cloture_fiscale import soldes
from axelcompta.closing.tva_periodique import (
    ParametresTvaInvalides,
    PeriodeTva,
    ca3_des_periodes,
    ca3_periode,
    echeance,
    ecriture_liquidation,
    periodes,
    verifier_parametres,
)
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

D = DossierId("d1")
MARS = PeriodeTva(date(2026, 3, 1), date(2026, 3, 31))
AVRIL = PeriodeTva(date(2026, 4, 1), date(2026, 4, 30))


def _recette(jour: date, ttc: int, tva: int, n: str) -> Ecriture:
    return Ecriture(
        EcritureId(f"d1:r{n}"),
        D,
        Journal.BQ,
        jour,
        "Uber",
        None,
        (
            LigneEcriture("512", Sens.DEBIT, Money(ttc)),
            LigneEcriture("706", Sens.CREDIT, Money(ttc - tva)),
            LigneEcriture("44571", Sens.CREDIT, Money(tva)),
        ),
    )


def _depense(jour: date, ttc: int, tva: int, n: str) -> Ecriture:
    return Ecriture(
        EcritureId(f"d1:d{n}"),
        D,
        Journal.BQ,
        jour,
        "Total",
        None,
        (
            LigneEcriture("6061", Sens.DEBIT, Money(ttc - tva)),
            LigneEcriture("44566", Sens.DEBIT, Money(tva)),
            LigneEcriture("512", Sens.CREDIT, Money(ttc)),
        ),
    )


def _autoliquidation(jour: date, tva: int) -> Ecriture:
    return Ecriture(
        EcritureId("d1:bolt"),
        D,
        Journal.OD,
        jour,
        "Commission Bolt",
        None,
        (
            LigneEcriture("44566", Sens.DEBIT, Money(tva), code_tva="autoliquidation"),
            LigneEcriture("44571", Sens.CREDIT, Money(tva), code_tva="autoliquidation"),
        ),
    )


def test_les_periodes_suivent_le_calendrier_et_l_exercice() -> None:
    mois = periodes(date(2026, 1, 1), date(2026, 12, 31), "mensuelle")
    trimestres = periodes(date(2026, 2, 15), date(2026, 12, 31), "trimestrielle")
    assert (len(mois), mois[2].cle) == (12, "2026-03")
    assert [t.cle for t in trimestres] == ["2026-T1", "2026-T2", "2026-T3", "2026-T4"]
    assert trimestres[0].debut == date(2026, 2, 15)  # borné au début d'exercice


def test_l_echeance_est_le_jour_du_mois_suivant_borne_a_sa_fin() -> None:
    assert echeance(MARS, 19) == date(2026, 4, 19)
    assert echeance(PeriodeTva(date(2026, 1, 1), date(2026, 1, 31)), 31) == date(2026, 2, 28)
    assert echeance(PeriodeTva(date(2026, 12, 1), date(2026, 12, 31)), 15) == date(2027, 1, 15)


def test_la_ca3_d_un_mois_egale_le_calcul_a_la_main() -> None:
    """Critère : 1 100 € TTC de courses (100 € de TVA à 10 %), 60 € de
    carburant (10 € de TVA) et 4 € de TVA autoliquidée sur Bolt."""
    ecritures = [
        _recette(date(2026, 3, 5), 110_000, 10_000, "1"),
        _depense(date(2026, 3, 8), 6_000, 1_000, "1"),
        _autoliquidation(date(2026, 3, 10), 400),
        _recette(date(2026, 4, 2), 11_000, 1_000, "2"),  # hors période
    ]
    ca3 = ca3_periode(ecritures, MARS)
    assert (ca3.collectee, ca3.autoliquidee, ca3.deductible) == (10_400, 400, 1_400)
    assert (ca3.due, ca3.credit) == (9_000, 0)
    assert {ligne.numero: ligne.centimes for ligne in ca3.lignes if ligne.numero}["28"] == 9_000


def test_un_credit_de_tva_se_reporte_sur_la_periode_suivante() -> None:
    ecritures = [
        _depense(date(2026, 3, 8), 120_000, 20_000, "1"),  # achat : crédit de 200 €
        _recette(date(2026, 4, 5), 330_000, 30_000, "2"),
    ]
    mars, avril = ca3_des_periodes(ecritures, [MARS, AVRIL])
    assert (mars.credit, mars.due) == (20_000, 0)
    assert (avril.credit_anterieur, avril.due) == (20_000, 10_000)


def test_la_liquidation_est_equilibree_et_la_liasse_reprend_la_somme_des_periodes() -> None:
    ecritures = [
        _recette(date(2026, 3, 5), 110_000, 10_000, "1"),
        _depense(date(2026, 3, 8), 120_000, 20_000, "1"),
        _recette(date(2026, 4, 5), 330_000, 30_000, "2"),
    ]
    mars, avril = ca3_des_periodes(ecritures, [MARS, AVRIL])
    liquidations = [ecriture_liquidation(D, ecritures, c) for c in (mars, avril)]
    for liquidation in liquidations:
        assert liquidation is not None
        verifier_equilibre(liquidation)
    toutes = ecritures + [e for e in liquidations if e is not None]
    solde = soldes(tuple(toutes))
    assert solde.get("44571", 0) == solde.get("44566", 0) == solde.get("44567", 0) == 0
    assert solde["44551"] == -20_000  # 300 € collectés en avril, moins 100 € de crédit de mars
    annuelle = declaration_ca3(soldes(tuple(ecritures)))
    assert annuelle["DUE"] == mars.collectee + avril.collectee - mars.deductible - avril.deductible


@pytest.mark.parametrize(("periodicite", "jour"), [("annuelle", 19), ("mensuelle", 0)])
def test_des_parametres_illisibles_sont_refuses(periodicite: str, jour: int) -> None:
    with pytest.raises(ParametresTvaInvalides):
        verifier_parametres(periodicite, jour)
