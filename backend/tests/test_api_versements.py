"""AXE-821 : le chauffeur voit le détail de ses versements, pas le gestionnaire."""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId
from axelcompta.demo_api import get_settlements
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
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
