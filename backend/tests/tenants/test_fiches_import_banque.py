"""AXE-973 : rattacher le compte d'un FEC à un compte connu, saisir un solde."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.tenants.fiches_import_banque import (
    ajouter_solde,
    racine,
    rattachements,
    rattacher,
    retirer_solde,
    soldes_saisis,
)

AUJOURD_HUI = date(2026, 11, 18)


def test_un_compte_de_fec_se_rattache_et_se_detache() -> None:
    champs = rattacher({}, "fec:5120020", "digi:67499359")
    assert rattachements(champs) == {"fec:5120020": "digi:67499359"}
    champs = rattacher(champs, "doc:abc", "fec:5120020")
    assert racine("doc:abc", rattachements(champs)) == "digi:67499359"
    assert rattachements(rattacher(champs, "fec:5120020", None)) == {"doc:abc": "fec:5120020"}


def test_un_rattachement_refuse_les_boucles_et_les_cles_inconnues() -> None:
    champs = rattacher({}, "fec:5120020", "fec:5120010")
    with pytest.raises(SaisieInvalide, match="boucle"):
        rattacher(champs, "fec:5120010", "fec:5120020")
    with pytest.raises(SaisieInvalide, match="inconnu"):
        rattacher({}, "banque", "digi:1")
    with pytest.raises(SaisieInvalide, match="référence"):
        rattacher({}, "digi:1", "fec:512")


def test_un_solde_lu_sur_un_releve_se_saisit_et_se_retire() -> None:
    champs = ajouter_solde(
        {}, "digi:67499359", date(2025, 9, 30), "1 367,16 €", "Relevé Bred sept. 2025", AUJOURD_HUI
    )
    champs = ajouter_solde(champs, "fec:5120010", date(2023, 5, 31), "-12.50", "", AUJOURD_HUI)
    assert [(s.compte, s.cts, s.source) for s in soldes_saisis(champs)] == [
        ("digi:67499359", 136716, "Relevé Bred sept. 2025 (saisi)"),
        ("fec:5120010", -1250, "Relevé (saisi)"),
    ]
    assert [s.cts for s in soldes_saisis(retirer_solde(champs, 0))] == [-1250]


def test_un_solde_mal_saisi_est_refuse() -> None:
    with pytest.raises(SaisieInvalide, match="Montant"):
        ajouter_solde({}, "digi:1", date(2025, 9, 30), "beaucoup", "", AUJOURD_HUI)
    with pytest.raises(SaisieInvalide, match="date future"):
        ajouter_solde({}, "digi:1", date(2027, 1, 1), "10", "", AUJOURD_HUI)
    with pytest.raises(SaisieInvalide, match="introuvable"):
        retirer_solde({}, 0)
