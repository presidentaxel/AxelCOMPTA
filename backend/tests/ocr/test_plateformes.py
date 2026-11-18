"""AXE-943 : récapitulatifs de plateformes lus par l'OCR."""

from __future__ import annotations

from axelcompta.ocr.categories import Contexte
from axelcompta.ocr.plateformes import RELEVE_PLATEFORME, mois_calendaire


def _lu(debut: str, fin: str, **montants: int) -> dict[str, object]:
    return {
        "plateforme": "bolt",
        "siren": "",
        "periode_debut": debut,
        "periode_fin": fin,
        "montants": [{"nom": k, "valeur_cts": v} for k, v in montants.items()],
    }


def test_un_recap_bolt_mensuel_compte_comme_celui_du_lecteur_exact() -> None:
    lu = _lu(
        "2025-02-01",
        "2025-02-28",
        courses_cts=300000,
        autres_cts=5000,
        frais_cts=75000,
        net_cts=230000,
    )
    assert RELEVE_PLATEFORME.controler(lu, Contexte()) == []
    donnees = RELEVE_PLATEFORME.donnees(lu)
    assert (donnees["type"], donnees["plateforme"], donnees["mois"]) == (
        "recap_plateforme",
        "bolt",
        "2025-02",
    )


def test_un_net_qui_ne_tombe_pas_juste() -> None:
    lu = _lu("2025-02-01", "2025-02-28", courses_cts=300000, frais_cts=75000, net_cts=230000)
    assert RELEVE_PLATEFORME.controler(lu, Contexte()) == [
        "Courses 3 000,00 € + autres 0,00 € − frais 750,00 € ≠ net 2 300,00 €."
    ]


def test_une_semaine_n_est_pas_un_mois() -> None:
    assert mois_calendaire(_lu("2025-02-03", "2025-02-09")) == ""
    assert mois_calendaire(_lu("2025-02-01", "2025-02-27")) == ""
    assert (
        RELEVE_PLATEFORME.donnees(_lu("2025-02-03", "2025-02-09"))["type"]
        == "releve_plateforme_periode"
    )
