from __future__ import annotations

from fastapi.testclient import TestClient

from axelcompta.api.app import create_app


def test_le_point_d_entree_sert_les_routes_et_repond_sante() -> None:
    app = create_app()
    chemins = {getattr(route, "path", "") for route in app.routes}
    assert "/dossiers" in chemins
    assert "/sante" in chemins

    reponse = TestClient(app).get("/sante")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok"}
