"""I4 côté API (AXE-806) : correction reportée, refus en 409."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.demo_api import create_app
from axelcompta.ledger.periodes import PeriodeClose
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_expert,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
    _sujets_a_trancher,
)


def test_une_imputation_sur_un_exercice_clos_est_datee_du_premier_jour_ouvert() -> None:
    client = _client_expert()
    ledger = _ledger_du_client(client)
    cible = _sujets_a_trancher(client, "DEMO_sophie")[0]
    originale = next(
        e for e in ledger.grand_livre(DossierId("DEMO_sophie")) if e.id == cible["ecriture_id"]
    )
    annee = originale.date.year
    ledger.clore(DossierId("DEMO_sophie"), date(annee, 1, 1), date(annee, 12, 31))

    reponse = client.post(
        "/expert/imputations",
        json={
            "dossier_id": "DEMO_sophie",
            "ecriture_id": cible["ecriture_id"],
            "compte": "6061",
            "motif": "Plein de la flotte",
        },
        headers=_en_tete_gestionnaire(),
    )

    assert reponse.status_code == 200
    nouvelle = next(
        e
        for e in ledger.grand_livre(DossierId("DEMO_sophie"))
        if e.id == EcritureId(reponse.json()["ecriture_id"])
    )
    assert nouvelle.date == date(annee + 1, 1, 1)


def test_une_periode_close_repond_409_avec_la_phrase() -> None:
    app = create_app()

    @app.get("/essai-periode-close")
    def essai() -> None:
        raise PeriodeClose(date(2025, 12, 15), (date(2025, 1, 1), date(2025, 12, 31)))

    reponse = TestClient(app).get("/essai-periode-close")

    assert reponse.status_code == 409
    assert "est clos" in reponse.json()["detail"]
