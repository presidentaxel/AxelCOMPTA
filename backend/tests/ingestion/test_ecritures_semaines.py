"""AXE-924 / AXE-926 : la recette d'un jour de plateforme. Seules les
courses portent la TVA ; pourboires, bonus et autres montants vont en 7068."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from axelcompta.ingestion.ecritures_semaines import COMPTE_HORS_COURSE, ecriture_recette
from axelcompta.ledger.models import Ecriture, Sens
from tests.test_revenus_rollee import JOUR

LUNDI = date(2026, 10, 5)
# 110 € gagnés dont 10 € de pourboire, Uber au jour : pas de commission.
GAGNE = replace(JOUR, gross_earnings_cts=110_00, commission_cts=0, net_payout_cts=110_00)


def _soldes(ecriture: Ecriture) -> dict[str, int]:
    soldes: dict[str, int] = {}
    for x in ecriture.lignes:
        signe = 1 if x.sens is Sens.CREDIT else -1
        soldes[x.compte] = soldes.get(x.compte, 0) + signe * x.montant.centimes
    return soldes


def _recette(pourboires: int, especes: int = 0) -> Ecriture:
    return ecriture_recette("j1", GAGNE, especes, "455", LUNDI, "assujetti_taux_reduit", pourboires)


def test_les_pourboires_ne_portent_pas_de_tva() -> None:
    """100 € de course à 10 % : 90,91 HT + 9,09 de TVA ; 10 € de pourboire
    en 7068, sans TVA ; la plateforme doit les 110 €."""
    soldes = _soldes(_recette(10_00))
    assert (soldes["706"], soldes["44571"], soldes[COMPTE_HORS_COURSE]) == (90_91, 9_09, 10_00)
    assert soldes["467"] == -110_00


def test_sans_pourboire_rien_ne_change() -> None:
    soldes = _soldes(_recette(0))
    assert COMPTE_HORS_COURSE not in soldes
    assert (soldes["706"], soldes["44571"], soldes["467"]) == (100_00, 10_00, -110_00)


def test_pourboires_et_especes_ensemble() -> None:
    soldes = _soldes(_recette(10_00, 30_00))
    assert (soldes["467"], soldes["455"], soldes[COMPTE_HORS_COURSE]) == (-80_00, -30_00, 10_00)


@pytest.mark.parametrize("pourboires", [-1, 110_01])
def test_un_pourboire_illisible_n_ecrit_rien(pourboires: int) -> None:
    with pytest.raises(ValueError, match="illisibles"):
        _recette(pourboires)


def test_un_jour_negatif_sans_hors_course_n_est_pas_bloque_par_le_controle() -> None:
    """Un ajustement Uber de −3,68 € sans course (vu en prod le 02/11)."""
    negatif = replace(GAGNE, gross_earnings_cts=-3_68, net_payout_cts=-3_68)
    ecriture = ecriture_recette("j2", negatif, 0, "455", LUNDI, "assujetti_taux_reduit", 0)
    assert COMPTE_HORS_COURSE not in _soldes(ecriture)
