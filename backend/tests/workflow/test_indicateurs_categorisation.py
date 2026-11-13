"""AXE-900 : part de chaque étage et délai opération → écriture imputée."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.workflow.indicateurs_categorisation import (
    OperationSuivie,
    calculer,
    centile,
    delai_heures,
)

MAINTENANT = datetime(2026, 11, 20, tzinfo=UTC)
JOUR = date(2026, 11, 10)
SYNCHRO = datetime(2026, 11, 11, 6, tzinfo=UTC)  # 30 h après le jour de l'opération


def _op(
    etage: str = "REGLE",
    categorie: str = "carburant",
    a_trancher: bool = False,
    decide_le: datetime | None = None,
) -> OperationSuivie:
    return OperationSuivie(etage, categorie, JOUR, SYNCHRO, a_trancher, decide_le)


def test_imputee_seule_le_delai_est_celui_de_la_synchro() -> None:
    assert delai_heures(_op(), MAINTENANT) == 30.0


def test_a_trancher_le_delai_va_jusqu_a_la_decision() -> None:
    decidee = _op("ML", "repas", True, datetime(2026, 11, 12, tzinfo=UTC))
    assert delai_heures(decidee, MAINTENANT) == 48.0


def test_encore_en_attente_le_delai_court_toujours() -> None:
    assert delai_heures(_op("ML", "repas", True), MAINTENANT) == 240.0


def test_une_recette_qui_attend_son_rapprochement_n_est_pas_mesuree() -> None:
    assert delai_heures(_op("REGLE", "recettes_plateformes", True), MAINTENANT) is None


def test_le_centile_prend_le_rang_le_plus_proche() -> None:
    assert centile([], 95) is None
    assert centile([float(n) for n in range(1, 21)], 95) == 19.0
    assert centile([5.0], 95) == 5.0


def test_les_parts_par_etage_et_par_issue() -> None:
    operations = [
        _op(),
        _op(),
        _op("ML", "peage_stationnement"),
        _op("BANQUE", "repas", True, datetime(2026, 11, 12, tzinfo=UTC)),
        _op("ML", "non_categorise_a_verifier", True),
    ]
    indicateurs = calculer(operations, MAINTENANT)
    assert indicateurs.operations == 5
    assert indicateurs.part_par_etage == {
        "regle": 40.0,
        "modele": 20.0,
        "banque": 20.0,
        "aucune": 20.0,
    }
    assert (indicateurs.part_imputee_seule, indicateurs.part_tranchee) == (60.0, 20.0)
    assert indicateurs.part_en_attente == 20.0
    assert indicateurs.delai_p95_heures == 240.0


def test_sans_operation_rien_n_est_mesure() -> None:
    indicateurs = calculer([], MAINTENANT)
    assert indicateurs.operations == 0 and indicateurs.delai_p95_heures is None
