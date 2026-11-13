"""AXE-888 : une proposition de l'IA s'affiche sur une opération à trancher."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.categorize.llm import VERSION_PROMPT, cle_libelle
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.demo_api import get_propositions_ia
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
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
