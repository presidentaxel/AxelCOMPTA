"""Taux de TVA choisi par l'expert (AXE-925)."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.expert import preparer_imputation
from axelcompta.workflow.taux_expert import (
    TauxExpertMemoire,
    TauxInconnu,
    cle_globale,
    montant_tva,
    resoudre_taux,
    taux_de_la_table,
    verifier_taux,
)
from axelcompta.workflow.tva_imputation import ventiler_taux

TENANT = TenantId("t")
DOSSIER = DossierId("d")


def test_la_ligne_gagne_sur_le_libelle_et_la_table() -> None:
    assert resoudre_taux("10", "20", "5.5") == ("10", "specifique")
    assert resoudre_taux(None, "20", "5.5") == ("20", "appris")
    assert resoudre_taux(None, None, "5.5") == ("5.5", "table")
    assert resoudre_taux(None, None, None) == (None, None)


def test_un_taux_hors_liste_est_refuse() -> None:
    assert verifier_taux("2.1") == "2.1"
    with pytest.raises(TauxInconnu):
        verifier_taux("19.6")


def test_le_meme_libelle_sans_ses_chiffres_partage_un_taux() -> None:
    assert cle_globale("TOTAL 23/11") == cle_globale("total 24/11")
    memoire = TauxExpertMemoire()
    memoire.poser(TENANT, DOSSIER, cle_globale("TOTAL 23/11"), "10")
    assert memoire.pour_dossiers(TENANT, (DOSSIER,))[DOSSIER][cle_globale("TOTAL 24/11")] == "10"
    assert memoire.pour_dossiers(TenantId("autre"), (DOSSIER,)) == {}


def test_la_table_propose_le_taux_hors_franchise() -> None:
    jour = date(2026, 3, 1)
    assert taux_de_la_table("carburant", jour, "reel_simplifie") == "20"
    assert taux_de_la_table("carburant", jour, "franchise") is None
    assert taux_de_la_table(None, jour, "reel_simplifie") is None


def test_ventiler_separe_la_tva_et_un_taux_nul_laisse_l_ecriture() -> None:
    origine = Ecriture(
        id=EcritureId("e1"),
        dossier_id=DOSSIER,
        journal=Journal.BQ,
        date=date(2026, 3, 2),
        libelle="TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture("512", Sens.CREDIT, Money(120_00)),
            LigneEcriture("471", Sens.DEBIT, Money(120_00)),
        ),
    )
    _inverse, nouvelle = preparer_imputation(origine, "6061", {origine.id})
    ventilee = ventiler_taux(nouvelle, "20")
    par_compte = {ligne.compte: ligne.montant.centimes for ligne in ventilee.lignes}
    assert par_compte == {"512": 120_00, "6061": 100_00, "44566": 20_00}
    assert ventiler_taux(nouvelle, "0").lignes == nouvelle.lignes
    assert montant_tva(120_00, "20") == 20_00
    assert montant_tva(120_00, "0") == 0
