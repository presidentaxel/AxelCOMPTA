"""AXE-871 : chaque décision garde ce que l'humain avait sous les yeux."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from axelcompta.core.ids import DossierId
from axelcompta.demo_api import get_decisions
from axelcompta.workflow.decisions import DecisionRepository
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _premiere_a_trancher,
)

SOPHIE = "DEMO_sophie"


def test_une_decision_puis_une_correction_gardent_leur_contexte() -> None:
    client = _client()
    ecriture_id = _premiere_a_trancher(client, SOPHIE)
    for route, categorie in (("decision", "usage_personnel"), ("correction", "carburant")):
        reponse = client.post(
            f"/dossiers/{SOPHIE}/transactions/{ecriture_id}/{route}",
            json={"categorie": categorie},
            headers=_en_tete(SOPHIE),
        )
        assert reponse.status_code == 200, reponse.text
    depot = cast(
        DecisionRepository, cast(FastAPI, client.app).dependency_overrides[get_decisions]()
    )
    premiere, seconde = [
        d for d in depot.lister_decisions(DossierId(SOPHIE)) if d.ecriture_id == ecriture_id
    ]
    assert premiere.contexte is not None and seconde.contexte is not None
    assert premiere.contexte.libelle and premiere.contexte.montant_cts != 0
    assert premiere.contexte.nature in ("confirmee", "corrigee", "sans_proposition")
    assert (seconde.contexte.proposee, seconde.contexte.nature) == (premiere.categorie, "corrigee")
