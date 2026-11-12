"""AXE-831 : reprise des dépenses imputées TTC avant la règle."""

from __future__ import annotations

from collections import Counter
from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser, id_contrepassation
from axelcompta.ledger.invariants import verifier_equilibre
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.reclassement import annuler_reclassements, projeter, reclasser
from axelcompta.workflow.reprise_tva import reprises_tva

D = DossierId("d1")
COMPTES: tuple[dict[str, str | None], dict[str, str]] = (
    {},
    {"carburant": "6061", "repas_et_receptions": "6257"},
)


def _operation(identifiant: str, compte: str, montant: int = 60_00) -> Ecriture:
    return Ecriture(
        id=EcritureId(identifiant),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", Sens.CREDIT, Money(montant)),
            LigneEcriture(compte, Sens.DEBIT, Money(montant)),
        ),
    )


def _soldes(ecritures: list[Ecriture]) -> Counter[str]:
    soldes: Counter[str] = Counter()
    for ecriture in ecritures:
        for ligne in ecriture.lignes:
            soldes[ligne.compte] += (1 if ligne.sens is Sens.DEBIT else -1) * ligne.montant.centimes
    return Counter({c: s for c, s in soldes.items() if s})


def _categories(**par_id: str) -> dict[EcritureId, str]:
    return {EcritureId(k): v for k, v in par_id.items()}


def test_une_operation_imputee_directement_recoit_sa_tva() -> None:
    plein = _operation("s1", "6061")
    (od,) = reprises_tva([plein], _categories(s1="carburant"), COMPTES, "reel_normal")
    verifier_equilibre(od)
    assert od.id == "s1:tva-1"
    assert _soldes([plein, od]) == Counter({"5121": -60_00, "6061": 50_00, "44566": 10_00})
    (vue,) = projeter([plein, od])
    assert [(x.compte, x.montant.centimes) for x in vue.lignes] == [
        ("5121", 60_00),
        ("6061", 50_00),
        ("44566", 10_00),
    ]


def test_la_reprise_est_idempotente() -> None:
    plein = _operation("s1", "6061")
    ods = reprises_tva([plein], _categories(s1="carburant"), COMPTES, "reel_normal")
    assert reprises_tva([plein, *ods], _categories(s1="carburant"), COMPTES, "reel_normal") == []


def test_ni_repas_ni_franchise_ne_bougent() -> None:
    repas = _operation("s1", "6257")
    plein = _operation("s2", "6061")
    categories = _categories(s1="repas_et_receptions", s2="carburant")
    assert reprises_tva([repas, plein], categories, COMPTES, "reel_normal")[0].id == "s2:tva-1"
    assert reprises_tva([repas, plein], categories, COMPTES, "franchise") == []


def test_une_decision_ttc_est_reecrite_avec_sa_tva() -> None:
    source = _operation("s1", "471")
    ancienne = reclasser(source, "carburant", [source], COMPTES)  # TTC, comme avant
    assert ancienne is not None
    ods = reprises_tva([source, ancienne], _categories(s1="carburant"), COMPTES, "reel_normal")
    assert len(ods) == 1
    assert _soldes([source, ancienne, *ods]) == Counter(
        {"5121": -60_00, "6061": 50_00, "44566": 10_00}
    )


def test_une_operation_encore_au_471_attend_sa_decision() -> None:
    source = _operation("s1", "471")
    assert reprises_tva([source], _categories(s1="carburant"), COMPTES, "reel_normal") == []


def test_la_contrepassation_annule_aussi_le_complement() -> None:
    plein = _operation("s1", "6061")
    (od,) = reprises_tva([plein], _categories(s1="carburant"), COMPTES, "reel_normal")
    annulations = annuler_reclassements(plein.id, [plein, od])
    assert [a.id for a in annulations] == [id_contrepassation(od.id)]
    assert _soldes([plein, od, contrepasser(plein), *annulations]) == Counter()


def test_un_exercice_clos_est_repris_dans_l_exercice_ouvert() -> None:
    plein = _operation("s1", "6061")
    clos = ((date(2026, 1, 1), date(2026, 6, 30)),)
    (od,) = reprises_tva([plein], _categories(s1="carburant"), COMPTES, "reel_normal", clos)
    assert od.date == date(2026, 7, 1)
