"""La frise d'un exercice terminé suit ses preuves, dans l'ordre."""

from __future__ import annotations

from axelcompta.workflow.jalons import JALONS_EXERCICE, etape_depuis_preuves


def test_compte_ferme_reste_a_compte_meme_avec_des_preuves() -> None:
    assert etape_depuis_preuves("invité", {"cloture"}) == "Compte"
    assert etape_depuis_preuves(None, set()) == "Compte"


def test_compte_ouvert_sans_preuve_est_en_suivi() -> None:
    assert etape_depuis_preuves("actif", set()) == "Suivi"


def test_la_frise_sarrete_au_premier_jalon_absent() -> None:
    assert etape_depuis_preuves("actif", {"cloture", "greffe_inpi"}) == "Clôture"


def test_tous_les_jalons_menent_a_la_signature_legale() -> None:
    toutes = {type_document for type_document, _nom in JALONS_EXERCICE}
    assert etape_depuis_preuves("actif", toutes) == "Signature légale"
