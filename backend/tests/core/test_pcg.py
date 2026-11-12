from __future__ import annotations

from axelcompta.core.pcg import COMPTE_BANQUE, est_compte_banque, nature_depuis_compte


def test_nature_depuis_compte() -> None:
    assert nature_depuis_compte("6061") == "charge"
    assert nature_depuis_compte("706") == "produit"
    assert nature_depuis_compte("101") == "autre"


def test_compte_banque() -> None:
    assert COMPTE_BANQUE == "512"
    assert est_compte_banque("5125")
    assert not est_compte_banque("580")


def test_la_tva_deductible_regroupe_44562_et_44566() -> None:
    from axelcompta.core.pcg import est_compte_tva_deductible

    assert est_compte_tva_deductible("44566") and est_compte_tva_deductible("44562")
    assert not est_compte_tva_deductible("44571") and not est_compte_tva_deductible("6061")
