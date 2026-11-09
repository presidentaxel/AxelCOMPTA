"""AXE-848 : l'ancien suffixe « (catégorie) » des libellés d'écriture."""

from __future__ import annotations

import pytest

from axelcompta.core.libelles import categorie_du_suffixe, sans_categorie


@pytest.mark.parametrize(
    ("libelle", "attendu", "categorie"),
    [
        ("Paiement carburant (carburant)", "Paiement carburant", "carburant"),
        ("XQZW 000 (non_categorise_a_verifier)", "XQZW 000", "non_categorise_a_verifier"),
        ("CB TOTAL ACCESS A6", "CB TOTAL ACCESS A6", None),
        # Un libellé de banque entre parenthèses, en majuscules, n'est pas touché.
        ("VIR SEPA (UBER BV)", "VIR SEPA (UBER BV)", None),
        ("Loyer (mars) payé", "Loyer (mars) payé", None),
    ],
)
def test_le_suffixe_de_categorie_se_lit_et_se_retire(
    libelle: str, attendu: str, categorie: str | None
) -> None:
    assert sans_categorie(libelle) == attendu
    assert categorie_du_suffixe(libelle) == categorie
