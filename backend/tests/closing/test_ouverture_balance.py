"""AXE-992 : les garde-fous d'une balance reprise comme bilan d'ouverture."""

from __future__ import annotations

from datetime import date

from axelcompta.closing.ouverture_balance import analyser_balance
from axelcompta.core.ids import DossierId

D = DossierId("D")
OUVERTURE = date(2026, 1, 1)
SOLDES = {"101300": -50000, "512000": 50000}


def test_une_balance_equilibree_de_la_veille_donne_les_a_nouveaux() -> None:
    analyse = analyser_balance(SOLDES, date(2025, 12, 31), "e", D, OUVERTURE, {})
    assert analyse.refus == ()
    assert analyse.a_nouveaux is not None
    assert analyse.attestation.startswith("J'atteste que cette balance")


def test_une_balance_d_une_autre_date_ou_desequilibree_est_refusee() -> None:
    autre = analyser_balance(SOLDES, date(2025, 6, 30), "e", D, OUVERTURE, {})
    assert autre.a_nouveaux is None
    assert autre.refus[0].startswith("Cette balance est arrêtée au 30/06/2025")
    fausse = analyser_balance(
        {**SOLDES, "512000": 50010}, date(2025, 12, 31), "e", D, OUVERTURE, {}
    )
    assert "La balance ne s'équilibre pas : écart de 0,10 €." in fausse.refus


def test_un_compte_hors_plan_se_met_en_correspondance() -> None:
    soldes = {"101300": -50000, "BQ01": 50000}
    refusee = analyser_balance(soldes, date(2025, 12, 31), "e", D, OUVERTURE, {})
    assert refusee.comptes_inconnus == ("BQ01",)
    reprise = analyser_balance(soldes, date(2025, 12, 31), "e", D, OUVERTURE, {"BQ01": "512100"})
    assert reprise.refus == ()
    assert reprise.a_nouveaux is not None
    assert {lg.compte for lg in reprise.a_nouveaux.lignes} == {"101300", "512100"}
