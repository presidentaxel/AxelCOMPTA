"""AXE-819 : les comptes reliés dans Rollee Connect, traduits et résumés."""

from __future__ import annotations

from datetime import UTC, datetime

from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_rollee import depuis_rollee, noms_plateformes, synthese
from axelcompta.packs.vtc_demo import charger_plateformes

D = DossierId("DIGI_1")
HIER = datetime(2026, 11, 10, tzinfo=UTC)
AUJOURD_HUI = datetime(2026, 11, 11, tzinfo=UTC)


def test_la_date_de_liaison_est_la_premiere_fois_vu_connecte() -> None:
    brut = {"id": "acc-1", "name": "Uber", "connected": True, "reconnecting": False}
    premier = depuis_rollee(D, brut, None, HIER)
    relu = depuis_rollee(D, brut, premier, AUJOURD_HUI)
    assert (premier.relie_le, relu.relie_le, relu.maj_le) == (HIER, HIER, AUJOURD_HUI)
    assert relu.etat == "connecte"


def test_les_etats_d_un_compte() -> None:
    deconnecte = depuis_rollee(D, {"id": "a", "name": "Bolt", "connected": False}, None, HIER)
    en_cours = depuis_rollee(
        D, {"id": "a", "name": "Bolt", "connected": False, "reconnecting": True}, None, HIER
    )
    assert (deconnecte.etat, en_cours.etat, deconnecte.relie_le) == (
        "a_reconnecter",
        "en_cours",
        None,
    )


def test_les_noms_de_plateformes_viennent_de_rollee_sans_doublon() -> None:
    assert noms_plateformes(["Uber", " bolt "], ["Bolt", "Heetch", ""]) == (
        "Bolt",
        "Heetch",
        "Uber",
    )


def test_la_synthese_compte_sans_montant_et_dit_ce_qui_manque() -> None:
    comptes = [
        depuis_rollee(D, {"id": "u", "name": "Uber", "connected": True}, None, HIER),
        depuis_rollee(D, {"id": "b", "name": "Bolt", "connected": False}, None, HIER),
    ]
    resume = synthese(comptes, ["uber", "bolt"], charger_plateformes())
    assert (resume.reliees, resume.attendues, resume.a_reconnecter) == (1, 2, 1)
    assert resume.manquantes == ("bolt",) and resume.non_declarees == ()
    sans_attente = synthese(comptes, [], charger_plateformes())
    assert sans_attente.non_declarees == () and sans_attente.attendues == 0
