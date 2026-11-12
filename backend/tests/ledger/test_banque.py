from __future__ import annotations

from datetime import date

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.core.pcg import est_compte_banque
from axelcompta.ledger.banque import (
    comptes_hors_banque,
    est_reclassement_bancaire,
    ligne_banque,
    montant_bancaire,
)
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens


def _ecriture(*lignes: LigneEcriture, journal: Journal = Journal.BQ) -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DossierId("D"),
        journal=journal,
        date=date(2026, 6, 1),
        libelle="TOTAL",
        reference_piece=None,
        lignes=lignes,
    )


def test_le_compte_de_banque_couvre_512_et_ses_sous_comptes() -> None:
    assert est_compte_banque("512")
    assert est_compte_banque("5121")
    assert est_compte_banque("51210")
    assert not est_compte_banque("51")
    assert not est_compte_banque("471")
    assert not est_compte_banque("6512")


def test_le_montant_bancaire_se_lit_sur_un_sous_compte() -> None:
    depense = _ecriture(
        LigneEcriture("5123", Sens.CREDIT, Money(6_000)),
        LigneEcriture("6061", Sens.DEBIT, Money(6_000)),
    )
    recette = _ecriture(
        LigneEcriture("5121", Sens.DEBIT, Money(10_000)),
        LigneEcriture("471", Sens.CREDIT, Money(10_000)),
    )
    assert montant_bancaire(depense) == -6_000
    assert montant_bancaire(recette) == 10_000
    assert comptes_hors_banque(depense) == ["6061"]
    ligne = ligne_banque(recette)
    assert ligne is not None and ligne.compte == "5121"


def test_une_od_sans_banque_na_pas_de_montant_bancaire() -> None:
    od = _ecriture(
        LigneEcriture("471", Sens.CREDIT, Money(500)),
        LigneEcriture("6061", Sens.DEBIT, Money(500)),
        journal=Journal.OD,
    )
    assert ligne_banque(od) is None
    assert montant_bancaire(od) == 0
    assert not est_reclassement_bancaire(od)


def test_un_mouvement_entre_banques_est_un_reclassement() -> None:
    ventilation = _ecriture(
        LigneEcriture("5122", Sens.DEBIT, Money(1_000)),
        LigneEcriture("512", Sens.CREDIT, Money(1_000)),
        journal=Journal.OD,
    )
    assert est_reclassement_bancaire(ventilation)
    assert comptes_hors_banque(ventilation) == []


def test_la_tva_deductible_n_est_pas_une_contrepartie() -> None:
    """AXE-831 : un plein avec sa TVA reste « en 6061 » pour les écrans."""
    from datetime import date

    from axelcompta.core.ids import DossierId, EcritureId
    from axelcompta.core.money import Money
    from axelcompta.ledger.banque import comptes_hors_banque
    from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens

    plein = Ecriture(
        id=EcritureId("e1"),
        dossier_id=DossierId("d1"),
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="CB TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("5121", Sens.CREDIT, Money(60_00)),
            LigneEcriture("6061", Sens.DEBIT, Money(50_00)),
            LigneEcriture("44566", Sens.DEBIT, Money(10_00)),
        ),
    )
    assert comptes_hors_banque(plein) == ["6061"]
