from __future__ import annotations

import pytest

from axelcompta.anomaly.instruction import RegistreInstructions, TransitionRefusee


def test_le_cycle_passe_par_l_instruction() -> None:
    registre = RegistreInstructions()
    assert registre.etat("a1") == "ouverte"
    assert registre.instruire("a1", "en_instruction", "louis", "") == "en_instruction"
    assert registre.instruire("a1", "justifiee", "louis", "ticket de carburant") == "justifiee"


def test_une_justification_sans_commentaire_est_refusee() -> None:
    registre = RegistreInstructions()
    registre.instruire("a1", "en_instruction", "louis", "")
    with pytest.raises(TransitionRefusee):
        registre.instruire("a1", "justifiee", "louis", "  ")


def test_on_ne_saute_pas_l_instruction() -> None:
    with pytest.raises(TransitionRefusee):
        RegistreInstructions().instruire("a1", "faux_positif", "louis", "")


def test_une_alerte_qualifiee_ne_change_plus() -> None:
    registre = RegistreInstructions()
    registre.instruire("a1", "en_instruction", "louis", "")
    registre.instruire("a1", "usage_personnel", "louis", "")
    with pytest.raises(TransitionRefusee):
        registre.instruire("a1", "faux_positif", "louis", "")
