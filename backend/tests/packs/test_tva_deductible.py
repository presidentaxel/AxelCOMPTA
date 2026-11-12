"""AXE-831 : TVA déductible estimée par catégorie."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from axelcompta.packs.tva_deductible import (
    RegleTva,
    _versions,
    regle_tva,
    tva_recuperable,
)

JOUR = date(2026, 3, 1)


def test_un_plein_de_60_euros_contient_10_euros_de_tva_recuperable() -> None:
    regle = regle_tva("carburant", JOUR, "reel_normal")
    assert regle is not None
    assert tva_recuperable(60_00, regle) == 10_00
    assert regle.compte == "44566"
    assert regle.code == "deductible_estimee_20"


def test_le_signe_du_montant_ne_change_rien() -> None:
    regle = regle_tva("carburant", JOUR, "reel_simplifie")
    assert regle is not None
    assert tva_recuperable(-60_00, regle) == 10_00


def test_un_dossier_en_franchise_ne_recupere_rien() -> None:
    assert regle_tva("carburant", JOUR, "franchise") is None


@pytest.mark.parametrize(
    "categorie",
    ["repas_et_receptions", "frais_bancaires", "assurance_vehicule", "categorie_inconnue"],
)
def test_ce_qui_ne_se_recupere_pas_ne_donne_pas_de_regle(categorie: str) -> None:
    assert regle_tva(categorie, JOUR, "reel_normal") is None


def test_avant_la_table_rien_n_est_estime() -> None:
    assert regle_tva("carburant", date(2024, 12, 31), "reel_normal") is None


def test_l_achat_du_vehicule_va_en_tva_sur_immobilisation() -> None:
    regle = regle_tva("immobilisation_vehicule", JOUR, "reel_normal")
    assert regle is not None and regle.compte == "44562"


def test_une_part_partielle_s_arrondit_au_centime() -> None:
    regle = RegleTva(taux=Decimal("20"), recuperable=80)
    # 100,00 TTC : 16,67 de TVA, dont 80 % = 13,34.
    assert tva_recuperable(100_00, regle) == 13_34


@pytest.mark.parametrize("montant", [1, 7, 99, 1_00, 12_345, 99_999_99])
@pytest.mark.parametrize("taux", ["20", "10", "5.5", "2.1"])
def test_la_tva_reste_entre_zero_et_le_montant(montant: int, taux: str) -> None:
    recuperable = tva_recuperable(montant, RegleTva(taux=Decimal(taux), recuperable=100))
    assert 0 <= recuperable <= montant
    hors_taxe = montant - recuperable
    # Le HT retrouvé redonne le TTC à un centime près.
    assert abs(round(hors_taxe * (1 + float(taux) / 100)) - montant) <= 1


def test_chaque_regle_qui_recupere_cite_sa_source() -> None:
    for version in _versions():
        for categorie, regle in version.categories.items():
            assert regle.source, f"{categorie} n'a pas de source"
            assert 0 <= regle.recuperable <= 100
