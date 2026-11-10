"""AXE-844 : un retrait d'espèces se tranche par une question dédiée."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import CATEGORIE_RETRAIT_ESPECES, RulesAndMlPipeline
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.demo_api import get_propositions
from axelcompta.ingestion.providers.base import NormalizedTransaction
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.packs.vtc_demo import charger_compte_par_categorie, charger_regles
from axelcompta.workflow.decisions import CATEGORIE_A_PRECISER
from axelcompta.workflow.synchro import COMPTE_ATTENTE, choisir_compte
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_expert,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

KARIM = "DEMO_karim"  # SASU à l'IS : usage personnel → 455
RETRAIT = EcritureId("DEMO_karim:digifactory-dab")


def _transaction(libelle: str, type_operation: str | None = None) -> NormalizedTransaction:
    return NormalizedTransaction(
        id=TransactionId("dab"),
        dossier_id=DossierId(KARIM),
        date=date(2026, 3, 1),
        montant_cts=-100_00,
        libelle=libelle,
        source_provider="test",
        raw_payload={},
        type_operation=type_operation,
    )


@pytest.mark.parametrize(
    ("libelle", "type_operation"),
    [("RETRAIT DAB PARIS 11", None), ("CREDIT AGRICOLE 1203", "withdrawal")],
)
def test_un_retrait_reste_a_trancher_avec_sa_categorie(
    libelle: str, type_operation: str | None
) -> None:
    proposition = RulesAndMlPipeline(regles=charger_regles(), modele=None).categoriser(
        DossierId(KARIM), _transaction(libelle, type_operation)
    )
    assert proposition.categorie == CATEGORIE_RETRAIT_ESPECES
    assert choisir_compte(proposition, charger_compte_par_categorie()) == COMPTE_ATTENTE


def _client_avec_retrait() -> TestClient:
    # La file expert est lue par l'expert-comptable habilité (AXE-800).
    client = _client_expert()
    _ledger_du_client(client).enregistrer(
        Ecriture(
            id=RETRAIT,
            dossier_id=DossierId(KARIM),
            journal=Journal.BQ,
            date=date(2026, 3, 1),
            libelle="RETRAIT DAB PARIS 11 (retrait_especes)",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(100_00)),
                LigneEcriture("471", Sens.DEBIT, Money(100_00)),
            ),
        )
    )
    propositions = client.app.dependency_overrides[get_propositions]()  # type: ignore[attr-defined]
    propositions.enregistrer(
        RETRAIT,
        ProposedEntry(
            DossierId(KARIM), TransactionId("dab"), CATEGORIE_RETRAIT_ESPECES, Etage.REGLE, 0.95
        ),
    )
    return client


def _decider(client: TestClient, categorie: str) -> dict[str, object]:
    reponse = client.post(
        f"/dossiers/{KARIM}/transactions/{RETRAIT}/decision",
        json={"categorie": categorie},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def test_usage_personnel_d_une_sasu_va_en_455_sans_autre_question() -> None:
    """Critère du ticket : 100 € retirés, « pour moi » → 455."""
    vue = _decider(_client_avec_retrait(), "usage_personnel")
    assert (vue["compte"], vue["statut"]) == ("455", "validé")


def test_une_depense_d_activite_demande_son_ticket() -> None:
    client = _client_avec_retrait()
    _decider(client, "repas_et_receptions")
    sujets = client.get("/expert/file", headers=_en_tete_gestionnaire()).json()["sujets"]
    assert f"ticket:{RETRAIT}" in {s["id"] for s in sujets}


def test_je_ne_sais_plus_reste_en_attente_et_passe_a_l_expert() -> None:
    client = _client_avec_retrait()
    vue = _decider(client, CATEGORIE_A_PRECISER)
    assert (vue["compte"], vue["statut"]) == ("471", "à trancher")
    sujets = client.get("/expert/file", headers=_en_tete_gestionnaire()).json()["sujets"]
    (sujet,) = [s for s in sujets if s["id"] == f"trancher:{RETRAIT}"]
    assert sujet["cote"] == "gestionnaire"
    assert "ne sait plus" in sujet["detail"]


def test_sans_suffixe_le_ticket_est_demande_d_apres_la_proposition() -> None:
    """AXE-848 : la synchro n'écrit plus « (retrait_especes) » dans le
    libellé. La catégorie d'origine se lit dans la proposition enregistrée,
    et le ticket reste demandé ; le libellé affiché est celui de la banque."""
    client = _client_expert()
    nouveau = EcritureId("DEMO_karim:digifactory-dab2")
    _ledger_du_client(client).enregistrer(
        Ecriture(
            id=nouveau,
            dossier_id=DossierId(KARIM),
            journal=Journal.BQ,
            date=date(2026, 3, 2),
            libelle="RETRAIT DAB PARIS 11",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(100_00)),
                LigneEcriture("471", Sens.DEBIT, Money(100_00)),
            ),
        )
    )
    propositions = client.app.dependency_overrides[get_propositions]()  # type: ignore[attr-defined]
    propositions.enregistrer(
        nouveau,
        ProposedEntry(
            DossierId(KARIM), TransactionId("dab2"), CATEGORIE_RETRAIT_ESPECES, Etage.REGLE, 0.95
        ),
    )
    reponse = client.post(
        f"/dossiers/{KARIM}/transactions/{nouveau}/decision",
        json={"categorie": "repas_et_receptions"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text

    sujets = client.get("/expert/file", headers=_en_tete_gestionnaire()).json()["sujets"]

    (ticket,) = [s for s in sujets if s["id"] == f"ticket:{nouveau}"]
    assert ticket["libelle"] == "RETRAIT DAB PARIS 11"


def test_une_ancienne_ecriture_s_affiche_sans_sa_categorie() -> None:
    client = _client_avec_retrait()  # libellé « … (retrait_especes) », d'avant AXE-848
    operations = client.get(f"/dossiers/{KARIM}/transactions", headers=_en_tete(KARIM)).json()
    (retrait,) = [o for o in operations if o["ecriture_id"] == RETRAIT]
    assert retrait["libelle"] == "RETRAIT DAB PARIS 11"
