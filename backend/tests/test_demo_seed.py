"""Amorçage de la démo sur des implémentations en mémoire (la version
Postgres est dans tests/integration/test_demo_seed_postgres.py)."""

from __future__ import annotations

import functools

import pytest

import axelcompta.demo_seed as demo_seed
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_chauffeurs_type import construire_ledger
from axelcompta.demo_seed import (
    TENANT_DEMO,
    AmorcageIncompletError,
    amorcer_demo,
    poser_jalons_demo,
)
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.workflow.jalons import etape_depuis_preuves
from axelcompta.workflow.propositions import InMemoryPropositionRepository
from axelcompta.workflow.signature_memory import InMemorySignatureRepository


@pytest.fixture(autouse=True)
def _ledger_en_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_seed, "construire_ledger", functools.cache(construire_ledger))


def _depots() -> tuple[
    InMemoryDossierRepository, InMemoryLedgerService, InMemoryPropositionRepository
]:
    return InMemoryDossierRepository(), InMemoryLedgerService(), InMemoryPropositionRepository()


def test_amorcage_cree_les_3_dossiers_du_portefeuille_demo() -> None:
    dossiers, ledger, propositions = _depots()

    ecrits = amorcer_demo(dossiers, ledger, propositions)

    assert ecrits == ["DEMO_karim", "DEMO_sophie", "DEMO_yanis"]
    assert [d.id for d in dossiers.lister_par_tenant(TENANT_DEMO)] == ecrits
    assert dossiers.lister_par_tenant(TenantId("autre")) == ()


def test_amorcage_porte_identite_et_fin_d_exercice() -> None:
    dossiers, ledger, propositions = _depots()
    amorcer_demo(dossiers, ledger, propositions)
    karim = dossiers.obtenir(DossierId("DEMO_karim"))
    assert karim is not None and karim.identite is not None
    assert karim.identite.denomination == "AMRANI VTC"
    assert karim.fin_exercice().isoformat() == "2025-12-31"
    # Le capital est libéré dans le ledger : sans lui, bilan à capital nul.
    apport = [e for e in ledger.grand_livre(karim.id) if e.id.endswith("apport-capital")]
    assert len(apport) == 1


def test_amorcage_est_idempotent() -> None:
    dossiers, ledger, propositions = _depots()
    amorcer_demo(dossiers, ledger, propositions)
    nb = len(ledger.grand_livre(DossierId("DEMO_karim")))

    assert amorcer_demo(dossiers, ledger, propositions) == []
    assert len(ledger.grand_livre(DossierId("DEMO_karim"))) == nb


def test_ids_decritures_uniques_entre_dossiers() -> None:
    """Le pipeline numérote par dossier (`categorise-1`) : sans préfixe, deux
    dossiers auraient la même clé primaire en base."""
    dossiers, ledger, propositions = _depots()
    amorcer_demo(dossiers, ledger, propositions)

    ids = [
        e.id
        for d in ("DEMO_karim", "DEMO_sophie", "DEMO_yanis")
        for e in ledger.grand_livre(DossierId(d))
    ]

    assert len(ids) == len(set(ids))
    assert all(i.startswith("DEMO_") for i in ids)


def test_toute_ecriture_a_trancher_a_sa_proposition_dorigine() -> None:
    """Sans elle, la file de revue ne peut pas enregistrer l'étage et la
    confiance d'origine d'une décision (500 « incohérence interne »)."""
    dossiers, ledger, propositions = _depots()
    amorcer_demo(dossiers, ledger, propositions)
    sophie = DossierId("DEMO_sophie")

    a_trancher = [
        e for e in ledger.grand_livre(sophie) if any(ligne.compte == "471" for ligne in e.lignes)
    ]

    assert a_trancher
    assert all(propositions.obtenir(sophie, e.id) is not None for e in a_trancher)


def test_jalons_2025_placent_les_3_dossiers_a_des_etapes_differentes() -> None:
    dossiers, ledger, propositions = _depots()
    signatures = InMemorySignatureRepository()
    amorcer_demo(dossiers, ledger, propositions)

    assert poser_jalons_demo(dossiers, ledger, signatures)
    assert poser_jalons_demo(dossiers, ledger, signatures) == []

    def etape(dossier_id: str) -> str:
        preuves = {
            type_document
            for type_document in (
                "cloture",
                "validation_comptes",
                "greffe_inpi",
                "depot_impots",
                "signature_legale",
            )
            if signatures.dernier(DossierId(dossier_id), type_document) is not None
        }
        return etape_depuis_preuves("actif", preuves)

    assert etape("DEMO_karim") == "Clôture"
    assert etape("DEMO_sophie") == "Greffe"
    assert etape("DEMO_yanis") == "Signature légale"
    assert signatures.dernier(DossierId("DEMO_karim"), "greffe_inpi") is None


def test_amorcage_incomplet_est_refuse() -> None:
    dossiers, ledger, propositions = _depots()
    amorcer_demo(dossiers, ledger, propositions)
    ledger._par_dossier[DossierId("DEMO_karim")].pop()

    with pytest.raises(AmorcageIncompletError):
        amorcer_demo(dossiers, ledger, propositions)
