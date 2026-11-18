"""AXE-943 : les contrôles communs des lectures OCR."""

from __future__ import annotations

from axelcompta.ocr.controles import (
    controle_date,
    controle_siren,
    euros,
    iban_valide,
    montants,
    siren_valide,
)


def test_le_siren_a_sa_cle_de_luhn() -> None:
    assert siren_valide("908771033")  # KERFICE SERVICE
    assert not siren_valide("908771034")
    assert not siren_valide("90877103")


def test_l_iban_a_sa_cle() -> None:
    assert iban_valide("FR76 3000 6000 0112 3456 7890 189")
    assert not iban_valide("FR76 3000 6000 0112 3456 7890 188")


def test_un_siren_d_une_autre_societe_se_voit() -> None:
    assert controle_siren({"siren": "908771033"}, "908771033") == []
    assert controle_siren({"siren": ""}, "908771033") == []
    (erreur,) = controle_siren({"siren": "552100554"}, "908771033")
    assert "autre société" in erreur


def test_une_date_illisible_ou_absente() -> None:
    assert controle_date({"d": "2025-09-30"}, "d", "Clôture", True) == []
    assert controle_date({"d": ""}, "d", "Clôture", True) == ["Clôture : non lue."]
    assert controle_date({"d": "30/09/2025"}, "d", "Clôture", False) == [
        "Clôture : date illisible (30/09/2025)."
    ]


def test_les_montants_lus_et_leur_ecriture() -> None:
    lu = {"montants": [{"nom": "capital_cts", "valeur_cts": 100000}, {"nom": "x"}]}
    assert montants(lu) == {"capital_cts": 100000}
    assert euros(-123456) == "−1 234,56 €"
