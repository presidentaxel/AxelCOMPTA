"""AXE-804 : les déficits repris à l'ouverture réduisent l'IS, et ce qui
n'est pas imputé passe à l'exercice suivant (2033-D ligne 870)."""

from __future__ import annotations

from datetime import date

from axelcompta.closing.cloture_fiscale import cloturer_fiscalement, ecritures_de_cloture
from axelcompta.closing.models import ParametresCloture
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

DOSSIER = DossierId("D1")


def _benefice(euros: int) -> tuple[Ecriture, ...]:
    return (
        Ecriture(
            id=EcritureId("v1"),
            dossier_id=DOSSIER,
            journal=Journal.VE,
            date=date(2026, 6, 30),
            libelle="ventes",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.DEBIT, Money(euros * 100)),
                LigneEcriture("706", Sens.CREDIT, Money(euros * 100)),
            ),
        ),
    )


def _parametres(deficits: int) -> ParametresCloture:
    return ParametresCloture(
        exercice_debut=date(2026, 1, 1),
        exercice_fin=date(2026, 12, 31),
        forme_juridique="SASU",
        soumis_is=True,
        deficits_anterieurs=deficits,
    )


def _impot_cts(deficits: int) -> int:
    ecritures = ecritures_de_cloture(DOSSIER, _benefice(10_000), _parametres(deficits))
    return sum(
        lg.montant.centimes for e in ecritures for lg in e.lignes if lg.compte.startswith("695")
    )


def test_le_deficit_reporte_reduit_l_is() -> None:
    sans, avec = _impot_cts(0), _impot_cts(4_000)
    assert sans > 0
    # 10 000 € de bénéfice, 4 000 € de déficit imputé : IS sur 6 000 €.
    assert avec * 10 == sans * 6


def test_le_deficit_non_impute_passe_a_l_exercice_suivant() -> None:
    liasse = cloturer_fiscalement(DOSSIER, "2026", _benefice(10_000), _parametres(15_000))
    assert liasse.cases["2033D.870"] == 5_000 * 100  # centimes


def test_au_passage_d_exercice_le_reste_est_reporte_a_l_is_seulement() -> None:
    import dataclasses

    from axelcompta.core.ids import TenantId
    from axelcompta.exercices import _deficits_reportables
    from axelcompta.tenants.models import Dossier

    dossier = Dossier(
        id=DOSSIER,
        tenant_id=TenantId("T"),
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        nom="D1",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2026, 1, 1),
        deficits_anterieurs_euros=15_000,
    )
    assert _deficits_reportables(dossier, _benefice(10_000), _parametres(15_000)) == 5_000
    a_l_ir = dataclasses.replace(_parametres(15_000), soumis_is=False)
    assert _deficits_reportables(dossier, _benefice(10_000), a_l_ir) == 0
