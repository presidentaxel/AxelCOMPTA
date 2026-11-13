"""AXE-821 : le chauffeur voit le détail de ses versements, pas le gestionnaire."""

from __future__ import annotations

from dataclasses import replace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from axelcompta.api.routes import get_services_rollee, get_settlements
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
from tests.test_plateformes_rollee import _services
from tests.test_revenus_rollee import SEMAINE, _stocke


def _client() -> TestClient:
    client = _client_et_stubs()[0]
    depot = SettlementsMemoire()
    stocke = _stocke(replace(SEMAINE, dossier_id=DossierId("DEMO_karim")))
    depot.enregistrer([replace(stocke, etat="reconcilie", ecriture_id="S1")])
    client.app.dependency_overrides[get_settlements] = lambda: depot  # type: ignore[attr-defined]
    return client


def test_le_chauffeur_lit_brut_commission_et_verse() -> None:
    reponse = _client().get(
        "/dossiers/DEMO_karim/versements-plateformes", headers=_en_tete("DEMO_karim")
    )
    assert reponse.status_code == 200
    ((versement,),) = (reponse.json(),)
    assert (versement["brut_cts"], versement["commission_cts"], versement["verse_cts"]) == (
        1_040_00,
        192_00,
        848_00,
    )
    assert versement["etat"] == "reconcilie"


def test_le_gestionnaire_n_a_pas_acces_aux_montants() -> None:
    reponse = _client().get(
        "/dossiers/DEMO_karim/versements-plateformes", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code in (401, 403)


def _client_avec_a_verifier() -> TestClient:
    client = _client_et_stubs()[0]
    depot = SettlementsMemoire()
    semaine = replace(SEMAINE, dossier_id=DossierId("DEMO_karim"))
    depot.enregistrer(
        [
            replace(_stocke(semaine), etat="reconcilie", ecriture_id="S1"),
            replace(
                _stocke(replace(semaine, platform="bolt")),
                id="bolt:1",
                etat="a_verifier",
                motif="plusieurs virements possibles",
            ),
        ]
    )
    client.app.dependency_overrides[get_settlements] = lambda: depot  # type: ignore[attr-defined]
    return client


def test_a_traiter_ne_reprend_que_les_releves_a_verifier_avec_leur_motif() -> None:
    reponse = _client_avec_a_verifier().get(
        "/dossiers/DEMO_karim/versements-plateformes/a-verifier", headers=_en_tete("DEMO_karim")
    )
    assert reponse.status_code == 200
    assert [(v["etat"], v["motif"]) for v in reponse.json()] == [
        ("a_verifier", "plusieurs virements possibles")
    ]


def test_le_gestionnaire_voit_le_nombre_a_verifier_sans_montant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AXELCOMPTA_CLE_INTEGRATIONS", Fernet.generate_key().decode())
    client = _client_avec_a_verifier()
    refuse = client.get(
        "/dossiers/DEMO_karim/versements-plateformes/a-verifier", headers=_en_tete_gestionnaire()
    )
    assert refuse.status_code in (401, 403)
    services, _journal, _ = _services()
    services.comptes = ComptesRolleeMemoire()
    client.app.dependency_overrides[get_services_rollee] = lambda: services  # type: ignore[attr-defined]
    synthese = client.get(
        "/dossiers/DEMO_karim/plateformes/synthese", headers=_en_tete_gestionnaire()
    )
    assert synthese.status_code == 200
    assert synthese.json()["versements_a_verifier"] == 1
    assert not any("cts" in cle for cle in synthese.json())
