from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, EcritureId, TenantId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.statuts import configuration_de
from axelcompta.workflow.revue import CategorieInconnueError, resoudre_ecriture_a_trancher

COMPTES = {"carburant": "6061"}


def _comptes_statut(forme: str, regime: str) -> dict[str, str | None]:
    dossier = Dossier(
        id=DossierId("d1"),
        tenant_id=TenantId("t"),
        forme_juridique=forme,
        regime_imposition=regime,
        regime_tva="reel_normal",
        nom="d1",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2026, 1, 1),
    )
    return configuration_de(dossier).comptes_categories_statut()


SOCIETE = _comptes_statut("EURL", "IS")


def _ecriture_a_trancher(montant_cts: int = 68_00) -> Ecriture:
    return Ecriture(
        id=EcritureId("e1"),
        dossier_id=DossierId("d1"),
        journal=Journal.BQ,
        date=date(2026, 9, 7),
        libelle="CB ZARA FRANCE (usage_personnel_suspect)",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte="512", sens=Sens.CREDIT, montant=Money(montant_cts)),
            LigneEcriture(compte="471", sens=Sens.DEBIT, montant=Money(montant_cts)),
        ),
    )


@pytest.mark.parametrize(
    ("forme", "regime", "compte"),
    [("EURL", "IS", "455"), ("SASU", "IS", "455"), ("EURL", "IR", "455"), ("EI", "IR", "108")],
)
def test_usage_personnel_suit_la_matrice(forme: str, regime: str, compte: str) -> None:
    resolue = resoudre_ecriture_a_trancher(
        _ecriture_a_trancher(), "usage_personnel", _comptes_statut(forme, regime), COMPTES
    )
    assert {ligne.compte for ligne in resolue.lignes} == {"512", compte}


def test_reclassification_vers_une_categorie_normale_du_pack() -> None:
    """Sophie peut aussi être blanchie : la dépense n'était pas personnelle,
    juste mal catégorisée par le pipeline (doc 05 §5)."""
    ecriture = _ecriture_a_trancher()
    resolue = resoudre_ecriture_a_trancher(ecriture, "carburant", SOCIETE, COMPTES)
    assert {ligne.compte for ligne in resolue.lignes} == {"512", "6061"}


def test_montant_et_sens_inchanges_par_la_reclassification() -> None:
    ecriture = _ecriture_a_trancher(68_00)
    resolue = resoudre_ecriture_a_trancher(ecriture, "usage_personnel", SOCIETE, COMPTES)
    ligne_455 = next(ligne for ligne in resolue.lignes if ligne.compte == "455")
    assert ligne_455.sens is Sens.DEBIT
    assert ligne_455.montant.centimes == 68_00


def test_categorie_inconnue_du_pack_leve_plutot_que_deviner() -> None:
    ecriture = _ecriture_a_trancher()
    with pytest.raises(CategorieInconnueError):
        resoudre_ecriture_a_trancher(ecriture, "categorie_qui_nexiste_pas", SOCIETE, COMPTES)


def test_micro_entreprise_usage_personnel_signale_sans_ecriture() -> None:
    comptes = _comptes_statut("EI", "micro")
    assert comptes["usage_personnel"] is None
    with pytest.raises(CategorieInconnueError, match="signalé sans écriture"):
        resoudre_ecriture_a_trancher(_ecriture_a_trancher(), "usage_personnel", comptes, COMPTES)


@pytest.mark.parametrize(
    ("forme", "regime", "compte"),
    [("SASU", "IS", "421"), ("SAS", "IS", "421"), ("EURL", "IS", "644"), ("EI", "IR", "108")],
)
def test_la_remuneration_du_dirigeant_suit_la_forme(forme: str, regime: str, compte: str) -> None:
    resolue = resoudre_ecriture_a_trancher(
        _ecriture_a_trancher(), "remuneration_dirigeant", _comptes_statut(forme, regime), COMPTES
    )
    assert {ligne.compte for ligne in resolue.lignes} == {"512", compte}


def test_la_remuneration_d_un_gerant_de_sarl_se_precise_plutot_que_se_devine() -> None:
    with pytest.raises(CategorieInconnueError, match="majoritaire ou non"):
        resoudre_ecriture_a_trancher(
            _ecriture_a_trancher(), "remuneration_dirigeant", _comptes_statut("SARL", "IS"), COMPTES
        )


@pytest.mark.parametrize(
    ("forme", "regime", "categorie", "compte"),
    [
        ("SASU", "IS", "cotisations_dirigeant", "431"),
        ("EURL", "IS", "cotisations_dirigeant", "646"),
        ("EI", "IR", "cotisations_dirigeant", "646"),
        ("SASU", "IS", "prelevement_source_paie", "4421"),
        ("SASU", "IS", "dividendes", "457"),
        ("EURL", "IS", "impots_dividendes", "4423"),
    ],
)
def test_categories_de_paie_et_de_dividendes_selon_le_statut(
    forme: str, regime: str, categorie: str, compte: str
) -> None:
    resolue = resoudre_ecriture_a_trancher(
        _ecriture_a_trancher(), categorie, _comptes_statut(forme, regime), COMPTES
    )
    assert {ligne.compte for ligne in resolue.lignes} == {"512", compte}


@pytest.mark.parametrize(
    ("forme", "regime", "categorie", "message"),
    [
        ("EURL", "IR", "dividendes", "pas de dividendes"),
        ("EURL", "IS", "prelevement_source_paie", "bulletin de paie"),
        ("SARL", "IS", "cotisations_dirigeant", "majoritaire ou non"),
    ],
)
def test_categories_sans_objet_pour_le_statut(
    forme: str, regime: str, categorie: str, message: str
) -> None:
    with pytest.raises(CategorieInconnueError, match=message):
        resoudre_ecriture_a_trancher(
            _ecriture_a_trancher(), categorie, _comptes_statut(forme, regime), COMPTES
        )
