"""AXE-888 : une proposition de l'IA s'affiche sur une opération à trancher.
AXE-901 : la décision qui la confirme le garde."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.categorize.llm import VERSION_PROMPT, cle_libelle
from axelcompta.categorize.models import Etage, ProposedEntry
from axelcompta.categorize.rules_and_ml import CATEGORIE_PAR_DEFAUT
from axelcompta.core.ids import DossierId, EcritureId, TransactionId
from axelcompta.core.money import Money
from axelcompta.api.routes import get_decisions, get_propositions, get_propositions_ia
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.decisions import DecisionRepository
from axelcompta.workflow.propositions_ia import PropositionIa, PropositionsIaMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

SOPHIE = "DEMO_sophie"


def _depot(client: TestClient) -> PropositionsIaMemoire:
    app = cast(FastAPI, client.app)
    return cast(PropositionsIaMemoire, app.dependency_overrides[get_propositions_ia]())


def _transactions(client: TestClient) -> list[dict[str, object]]:
    reponse = client.get(f"/dossiers/{SOPHIE}/transactions", headers=_en_tete(SOPHIE))
    return cast(list[dict[str, object]], reponse.json())


def _sans_regle(client: TestClient) -> dict[str, object]:
    """Une opération qu'aucune règle ne reconnaît, ajoutée au grand livre de démo."""
    _ledger_du_client(client).enregistrer(
        Ecriture(
            id=EcritureId(f"{SOPHIE}:ia-1"),
            dossier_id=DossierId(SOPHIE),
            journal=Journal.BQ,
            date=date(2026, 3, 9),
            libelle="ZQX FOURNISSEUR INCONNU",
            reference_piece=None,
            lignes=(
                LigneEcriture("512", Sens.CREDIT, Money(42_00)),
                LigneEcriture("471", Sens.DEBIT, Money(42_00)),
            ),
        )
    )
    return next(t for t in _transactions(client) if t["ecriture_id"] == f"{SOPHIE}:ia-1")


def _proposition(libelle: str, categorie: str) -> PropositionIa:
    return PropositionIa(
        DossierId(SOPHIE),
        cle_libelle(libelle),
        VERSION_PROMPT,
        categorie,
        0.83,
        "",
        "claude-fable-5-2",
        datetime(2026, 11, 12, tzinfo=UTC),
    )


def test_l_ia_propose_quand_aucune_regle_ne_s_applique() -> None:
    client = _client()
    cible = _sans_regle(client)
    _depot(client).enregistrer([_proposition(str(cible["libelle"]), "telecommunications")])
    vue = next(t for t in _transactions(client) if t["ecriture_id"] == cible["ecriture_id"])
    assert (vue["proposition"], vue["origine_proposition"]) == ("telecommunications", "ia")
    assert vue["confiance_proposition"] == 0.83
    assert vue["statut"] == "à trancher"  # l'IA propose, elle n'impute jamais


def test_a_verifier_ne_s_affiche_pas() -> None:
    client = _client()
    cible = _sans_regle(client)
    _depot(client).enregistrer([_proposition(str(cible["libelle"]), "non_categorise_a_verifier")])
    vue = next(t for t in _transactions(client) if t["ecriture_id"] == cible["ecriture_id"])
    assert vue["origine_proposition"] != "ia"


def test_confirmer_la_proposition_de_l_ia_est_une_decision_confirmee() -> None:
    """AXE-901 : la décision garde ce que la file montrait (l'IA) et l'avis
    de chaque étage, pas seulement la proposition de la synchro."""
    client = _client()
    cible = _sans_regle(client)
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_propositions]().enregistrer(
        EcritureId(str(cible["ecriture_id"])),
        ProposedEntry(
            DossierId(SOPHIE), TransactionId("ia-1"), CATEGORIE_PAR_DEFAUT, Etage.ML, 0.2
        ),
    )
    _depot(client).enregistrer([_proposition(str(cible["libelle"]), "telecommunications")])
    reponse = client.post(
        f"/dossiers/{SOPHIE}/transactions/{cible['ecriture_id']}/decision",
        json={"categorie": "telecommunications"},
        headers=_en_tete(SOPHIE),
    )
    assert reponse.status_code == 200, reponse.text
    depot = cast(DecisionRepository, app.dependency_overrides[get_decisions]())
    (decision,) = [
        d
        for d in depot.lister_decisions(DossierId(SOPHIE))
        if d.ecriture_id == cible["ecriture_id"]
    ]
    contexte = decision.contexte
    assert contexte is not None
    assert (contexte.proposee, contexte.etage_propose, contexte.nature) == (
        "telecommunications",
        "LLM",
        "confirmee",
    )
    assert contexte.avis["synchro"] == {
        "etage": "ML",
        "categorie": CATEGORIE_PAR_DEFAUT,
        "confiance": 0.2,
    }
    assert contexte.avis["ia"]["modele"] == "claude-fable-5-2"
