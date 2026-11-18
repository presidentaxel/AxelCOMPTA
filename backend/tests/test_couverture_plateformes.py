"""AXE-987 : ce que Rollee, la banque et les documents disent de chaque
plateforme, mois par mois."""

from __future__ import annotations

from datetime import date

from axelcompta.couverture_plateformes import VirementVu, couverture, libelle_mois

LUNDI_SEPT = date(2025, 9, 8)
LUNDI_OCT = date(2025, 10, 6)
LUNDI_NOV = date(2025, 11, 3)
AUJOURD_HUI = date(2025, 12, 15)


def _etats(**kwargs: object) -> dict[str, str]:
    (uber,) = couverture(**kwargs)  # type: ignore[arg-type]
    return {m.mois: m.etat for m in uber.mois}


def test_un_virement_sans_jour_rollee_est_a_completer() -> None:
    virements = [
        VirementVu("uber", LUNDI_SEPT, 50_000),
        VirementVu("uber", LUNDI_SEPT, 25_000),
        VirementVu("uber", LUNDI_NOV, 40_000),
    ]
    jours = [("uber", date(2025, 11, 4))]
    (uber,) = couverture(jours, virements, [], date(2025, 9, 1), AUJOURD_HUI)
    assert {m.mois: m.etat for m in uber.mois} == {
        "2025-09": "a_completer",
        "2025-10": "sans_activite",
        "2025-11": "rollee",
        "2025-12": "sans_activite",
    }
    (phrase,) = uber.a_completer
    assert phrase.startswith("Uber, septembre 2025 : 2 virement(s) en banque (750,00 €)")


def test_un_recapitulatif_depose_couvre_le_mois() -> None:
    etats = _etats(
        jours=[],
        virements=[VirementVu("uber", LUNDI_OCT, 30_000)],
        documents=[("uber", "2025-10")],
        depuis=date(2025, 10, 1),
        aujourd_hui=date(2025, 10, 31),
    )
    assert etats == {"2025-10": "document"}


def test_rollee_sans_banque_renvoie_a_la_banque() -> None:
    etats = _etats(
        jours=[("uber", date(2025, 10, 7))],
        virements=[],
        documents=[],
        depuis=date(2025, 10, 1),
        aujourd_hui=date(2025, 10, 31),
    )
    assert etats == {"2025-10": "banque"}


def test_un_debut_de_rollee_en_milieu_de_mois_laisse_les_semaines_d_avant() -> None:
    """Rollee commence le 17/02 : les virements des semaines d'avant manquent."""
    virements = [
        VirementVu("uber", date(2026, 2, 2), 10_000),
        VirementVu("uber", date(2026, 2, 16), 20_000),
    ]
    jours = [("uber", date(2026, 2, 17))]
    (uber,) = couverture(jours, virements, [], date(2026, 2, 1), date(2026, 2, 28))
    (fevrier,) = uber.mois
    assert (fevrier.etat, fevrier.virements, fevrier.verse_cts) == ("a_completer", 1, 10_000)


def test_sans_donnee_rien_a_dire() -> None:
    assert couverture([], [], [], None, AUJOURD_HUI) == []
    assert libelle_mois("2025-08") == "août 2025"


def test_ni_banque_ni_rollee_ce_n_est_pas_sans_activite() -> None:
    """AXE-988 : SYBD n'a pas de banque connectée ; janvier et février 2026
    n'ont ni banque ni Rollee : on ne sait pas, ce n'est pas « sans activité »."""
    jours = [("uber", date(2026, 3, 29))]
    (uber,) = couverture(jours, [], [], date(2026, 1, 1), date(2026, 3, 31), mois_banque=set())
    assert {m.mois: m.etat for m in uber.mois} == {
        "2026-01": "inconnu",
        "2026-02": "inconnu",
        "2026-03": "banque",
    }
    assert uber.a_completer == (
        "Uber, de janvier 2026 à février 2026 : ni banque ni Rollee. Déposez les relevés "
        "bancaires, ou les récapitulatifs de la plateforme.",
    )


def test_un_mois_avec_banque_sans_la_plateforme_est_sans_activite() -> None:
    (uber,) = couverture(
        [("uber", date(2026, 3, 3))], [], [], date(2026, 2, 1), date(2026, 3, 31), {"2026-02"}
    )
    assert uber.mois[0].etat == "sans_activite"


def test_la_frise_commence_au_premier_recapitulatif_depose() -> None:
    """Les récapitulatifs 2025 se voient, même si l'exercice tenu commence en 2026."""
    (uber,) = couverture([], [], [("uber", "2025-11")], date(2026, 1, 1), date(2026, 1, 31))
    assert [(m.mois, m.etat) for m in uber.mois] == [
        ("2025-11", "document"),
        ("2025-12", "sans_activite"),
        ("2026-01", "sans_activite"),
    ]
