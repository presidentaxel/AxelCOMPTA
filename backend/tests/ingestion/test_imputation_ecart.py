"""AXE-969 : l'écart d'une semaine de plateforme, imputé en un clic."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ingestion.imputation_ecart import ecart_de_la_semaine, ecriture_imputation
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

D = DossierId("DIGI_22755")
LUNDI = date(2026, 10, 19)
PIECE = "uber:2026-10-19"


def _od(id_: str, debit: str, credit: str, cts: int, piece: str = PIECE) -> Ecriture:
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.OD,
        date=date(2026, 10, 25),
        libelle="x",
        reference_piece=piece,
        lignes=(
            LigneEcriture(debit, Sens.DEBIT, Money(cts)),
            LigneEcriture(credit, Sens.CREDIT, Money(cts)),
        ),
    )


# Rollee annonce 960,00 € ; Uber a versé 962,00 € : 2,00 € en trop.
TROP_VERSE = [
    _od("recette", "4671", "706", 96_000),
    _od("solde", "471", "4671", 96_200),
    _od("autre-semaine", "4671", "706", 5_000, piece="uber:2026-10-26"),
]


def test_l_ecart_se_lit_sur_la_creance_de_la_semaine() -> None:
    assert ecart_de_la_semaine(TROP_VERSE, "uber", LUNDI) == -200


def test_un_trop_verse_s_impute_au_credit_du_compte_choisi() -> None:
    od = ecriture_imputation(
        TROP_VERSE, D, "uber", LUNDI, "758", "Arrondi Uber", date(2026, 10, 25)
    )
    assert od is not None
    assert [(x.compte, x.sens, x.montant.centimes) for x in od.lignes] == [
        ("758", Sens.CREDIT, 200),
        ("4671", Sens.DEBIT, 200),
    ]
    assert "Arrondi Uber" in od.libelle
    # Rejouer : l'écart est soldé, rien de plus.
    assert ecart_de_la_semaine([*TROP_VERSE, od], "uber", LUNDI) == 0
    assert ecriture_imputation([*TROP_VERSE, od], D, "uber", LUNDI, "758", "x", od.date) is None


def test_un_encore_du_peut_aller_sur_un_autre_compte_bancaire() -> None:
    du = [_od("recette", "4671", "706", 50_000), _od("solde", "471", "4671", 30_000)]
    od = ecriture_imputation(du, D, "uber", LUNDI, "5123", "Versé sur le livret", LUNDI)
    assert od is not None
    assert [(x.compte, x.sens) for x in od.lignes] == [("5123", Sens.DEBIT), ("4671", Sens.CREDIT)]


def test_le_compte_doit_convenir_au_sens_de_l_ecart() -> None:
    with pytest.raises(SaisieInvalide, match="versé en trop"):
        ecriture_imputation(TROP_VERSE, D, "uber", LUNDI, "658", "x", LUNDI)
