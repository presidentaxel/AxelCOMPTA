from __future__ import annotations

from datetime import UTC, datetime

import pytest

from axelcompta.anomaly.instruction import RegistreInstructions, TransitionRefusee
from axelcompta.core.ids import DossierId

D = DossierId("d1")
LE = datetime(2026, 11, 5, 9, tzinfo=UTC)


def test_le_cycle_passe_par_l_instruction() -> None:
    registre = RegistreInstructions()
    assert registre.etats(D) == {}
    assert registre.instruire(D, "a1", "en_instruction", "louis", "", LE) == "en_instruction"
    assert (
        registre.instruire(D, "a1", "justifiee", "louis", "ticket de carburant", LE) == "justifiee"
    )
    assert registre.etats(D) == {"a1": "justifiee"}


def test_une_justification_sans_commentaire_est_refusee() -> None:
    registre = RegistreInstructions()
    registre.instruire(D, "a1", "en_instruction", "louis", "", LE)
    with pytest.raises(TransitionRefusee):
        registre.instruire(D, "a1", "justifiee", "louis", "  ", LE)


def test_on_ne_saute_pas_l_instruction() -> None:
    with pytest.raises(TransitionRefusee):
        RegistreInstructions().instruire(D, "a1", "faux_positif", "louis", "", LE)


def test_une_alerte_qualifiee_ne_change_plus() -> None:
    registre = RegistreInstructions()
    registre.instruire(D, "a1", "en_instruction", "louis", "", LE)
    registre.instruire(D, "a1", "usage_personnel", "louis", "", LE)
    with pytest.raises(TransitionRefusee):
        registre.instruire(D, "a1", "faux_positif", "louis", "", LE)


def test_l_historique_garde_chaque_changement_avec_son_auteur() -> None:
    registre = RegistreInstructions()
    registre.instruire(D, "a1", "en_instruction", "arthur", "", LE)
    registre.instruire(D, "a1", "justifiee", "louis", " péage pro ", LE)
    historique = registre.historique(D, "a1")
    assert [(e.etat, e.acteur, e.commentaire) for e in historique] == [
        ("en_instruction", "arthur", ""),
        ("justifiee", "louis", "péage pro"),
    ]
    assert registre.historique(DossierId("autre"), "a1") == ()
    assert registre.etats(DossierId("autre")) == {}
