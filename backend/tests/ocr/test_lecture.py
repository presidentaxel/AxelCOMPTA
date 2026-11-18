"""AXE-943 : Haiku, puis Sonnet si un contrôle échoue, puis un humain."""

from __future__ import annotations

from datetime import UTC, datetime

from axelcompta.ocr.categories import Categorie, Contexte
from axelcompta.ocr.lecture import HAIKU, SONNET, Appel, a_verifier, lire, traitement

LE = datetime(2026, 11, 18, 12, tzinfo=UTC)
CATEGORIE = Categorie(
    "test",
    "",
    textes=("valeur",),
    controler=lambda lu, _ctx: [] if lu.get("valeur") == "bon" else ["Valeur fausse."],
    resumer=lambda lu: f"Lu : {lu['valeur']}.",
    donnees=lambda lu: {"type": "test"},
)


def _appeler(reponses: dict[str, Appel]):  # type: ignore[no-untyped-def]
    appels: list[str] = []

    def appeler(modele: str, _c: Categorie, _b: bytes, _m: str) -> Appel:
        appels.append(modele)
        return reponses[modele]

    return appeler, appels


def test_haiku_juste_suffit() -> None:
    appeler, appels = _appeler({HAIKU: Appel({"valeur": "bon"}, 0.001)})
    lecture = lire(CATEGORIE, b"%PDF", "application/pdf", Contexte(), appeler)
    assert (lecture.acceptee, lecture.modele, appels) == (True, HAIKU, [HAIKU])
    statut, resume, donnees = traitement(CATEGORIE, lecture, {"ancien": 1}, LE)
    assert (statut, resume, donnees["type"], donnees["ancien"]) == (
        "traite",
        "Lu : bon.",
        "test",
        1,
    )
    assert a_verifier(donnees) == (False, [])


def test_un_controle_qui_echoue_fait_relire_par_sonnet() -> None:
    appeler, appels = _appeler(
        {HAIKU: Appel({"valeur": "faux"}, 0.001), SONNET: Appel({"valeur": "bon"}, 0.02)}
    )
    lecture = lire(CATEGORIE, b"%PDF", "application/pdf", Contexte(), appeler)
    assert (lecture.acceptee, lecture.modele, appels) == (True, SONNET, [HAIKU, SONNET])
    assert round(lecture.cout_usd, 3) == 0.021


def test_deux_echecs_vont_a_un_humain_avec_la_raison() -> None:
    appeler, _ = _appeler(
        {
            HAIKU: Appel(None, 0.0, "Réponse inutilisable (refusal)."),
            SONNET: Appel({"valeur": "faux"}, 0.02),
        }
    )
    lecture = lire(CATEGORIE, b"%PDF", "application/pdf", Contexte(), appeler)
    statut, resume, donnees = traitement(CATEGORIE, lecture, None, LE)
    assert statut == "a_traiter"
    assert resume == "À vérifier par un humain : Valeur fausse."
    assert a_verifier(donnees) == (True, ["Valeur fausse."])
    assert "type" not in donnees  # rien de la lecture refusée n'est retenu
