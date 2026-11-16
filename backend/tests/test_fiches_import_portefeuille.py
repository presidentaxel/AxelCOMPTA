"""AXE-952 : la synchro complète les fiches d'import du portefeuille."""

from __future__ import annotations

from axelcompta.fiches_import_portefeuille import plateforme_du_compte, resume


def test_le_nom_d_un_compte_rollee_donne_sa_plateforme() -> None:
    assert plateforme_du_compte("uber.com-fleet-rev") == "uber"
    assert plateforme_du_compte("free-now.com-rev") == "freenow"
    assert plateforme_du_compte("allocab-fleet-rev") == "allocab"
    assert plateforme_du_compte("deliveroo") is None


def test_le_resume_s_ajoute_a_celui_de_la_synchro() -> None:
    assert resume(15, 2) == "15 fiches d'import créées, 2 fiches d'import complétées"
    assert resume(1, 0) == "1 fiche d'import créée"
    assert resume(0, 0) == ""
