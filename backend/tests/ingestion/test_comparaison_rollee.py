"""AXE-928 : Rollee et la banque côte à côte."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from axelcompta.ingestion.comparaison_rollee import (
    JourRollee,
    annees,
    comparer,
    par_mois,
)
from axelcompta.ingestion.semaines_plateforme import Virement

AUJOURD_HUI = date(2026, 11, 20)
BANQUE = date(2026, 9, 1)
DIX = Decimal("0.10")


def _jour(le: date, gagne: int, rapproche: bool = False, plateforme: str = "uber") -> JourRollee:
    return JourRollee(plateforme, le, gagne, 0, 0, 0, gagne, rapproche)


def _virement(le: date, montant: int, semaine: date, nature: str = "hebdomadaire") -> Virement:
    return Virement(f"v-{le}-{montant}", "uber", le, montant, nature, semaine)  # type: ignore[arg-type]


def _etats(jours: list[JourRollee], virements: list[Virement]) -> list[tuple[date, str]]:
    return [(s.lundi, s.etat) for s in comparer(jours, virements, BANQUE, AUJOURD_HUI, DIX)]


def test_une_semaine_ecrite_en_compta_est_rapprochee() -> None:
    assert _etats([_jour(date(2026, 10, 5), 100_00, rapproche=True)], []) == [
        (date(2026, 10, 5), "rapprochee")
    ]


def test_avant_la_banque_rollee_seul() -> None:
    assert _etats([_jour(date(2026, 6, 1), 100_00)], []) == [(date(2026, 6, 1), "sans_banque")]


def test_sans_virement_il_manque_un_virement() -> None:
    """Pilote du 15/11 : MK DRIVING, juin-juillet, la banque est là mais
    aucun virement Uber n'arrive."""
    assert _etats([_jour(date(2026, 10, 5), 100_00)], []) == [
        (date(2026, 10, 5), "virement_manquant")
    ]


def test_une_semaine_payee_sans_jour_rollee() -> None:
    """Pilote du 15/11 : MK DRIVING reçoit des virements Bolt chaque semaine,
    mais aucun compte Bolt n'est relié chez Rollee."""
    virement = _virement(date(2026, 10, 12), 24_17, date(2026, 10, 5))
    assert _etats([], [virement]) == [(date(2026, 10, 5), "absente_de_rollee")]


def test_les_frais_de_0_99_par_retrait_instantane_sont_comptes() -> None:
    lundi = date(2026, 10, 5)
    virements = [
        _virement(date(2026, 10, 6), 49_01, lundi, "instantane"),
        _virement(date(2026, 10, 12), 50_00, lundi),
    ]
    (semaine,) = comparer([_jour(lundi, 100_00)], virements, BANQUE, AUJOURD_HUI, DIX)
    assert (semaine.etat, semaine.totaux.frais_cts, semaine.totaux.ecart_cts) == ("concorde", 99, 0)


def test_trop_verse_et_en_cours() -> None:
    lundi = date(2026, 10, 5)
    trop = [_virement(date(2026, 10, 12), 120_00, lundi)]
    assert _etats([_jour(lundi, 100_00)], trop) == [(lundi, "verse_en_trop")]
    recente = date(2026, 11, 9)
    assert _etats([_jour(recente, 100_00)], []) == [(recente, "en_cours")]


def test_le_rapport_d_une_annee_passee_calcule_la_tva_des_courses() -> None:
    """Un jour de 2024 : 110 € de courses TTC, 5 € de pourboires, 20 € de
    commission, 10 € en espèces. Rien en banque : rapport seul."""
    jour = JourRollee("uber", date(2024, 7, 3), 95_00, 20_00, 10_00, 5_00, 110_00, False)
    semaines = comparer([jour], [], None, AUJOURD_HUI, DIX)
    assert annees(semaines) == [2024]
    (mois,) = par_mois(semaines, 2024)
    t = mois.totaux
    assert (t.courses_ht_cts, t.tva_cts, t.hors_course_cts) == (100_00, 10_00, 5_00)
    assert (t.gagne_cts, t.commission_cts, t.especes_cts, t.du_cts) == (95_00, 20_00, 10_00, 85_00)
    assert mois.semaines[0].etat == "sans_banque"


def test_en_franchise_pas_de_tva() -> None:
    (semaine,) = comparer([_jour(date(2026, 10, 5), 100_00)], [], BANQUE, AUJOURD_HUI, None)
    assert (semaine.totaux.courses_ht_cts, semaine.totaux.tva_cts) == (100_00, 0)
