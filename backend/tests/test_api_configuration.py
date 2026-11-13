"""AXE-730 : le chauffeur confirme sa configuration ; la clôture et la liasse
attendent sa confirmation."""

from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_dossiers
from axelcompta.core.ids import DossierId
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = "DEMO_karim"


def _client_a_confirmer() -> TestClient:
    """Karim comme Sirene l'aurait proposé : SAS ou SASU, on ne sait pas."""
    client = _client()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    dossier = depot.obtenir(DossierId(KARIM))
    depot.reconfigurer_depuis_sirene(
        dataclasses.replace(dossier, forme_juridique="SAS", a_confirmer=("forme_juridique",))
    )
    return client


def test_le_chauffeur_voit_ce_qu_il_doit_confirmer() -> None:
    vue = _client_a_confirmer().get(f"/dossiers/{KARIM}/configuration", headers=_en_tete(KARIM))
    assert vue.status_code == 200
    corps = vue.json()
    assert (corps["forme_juridique"], corps["formes_proposees"]) == ("SAS", ["SAS", "SASU"])
    assert corps["a_confirmer"] == ["forme_juridique"]
    assert corps["raison_blocage"] == "Le dirigeant doit d'abord confirmer la forme juridique."


def test_la_liasse_et_la_cloture_attendent_la_confirmation() -> None:
    client = _client_a_confirmer()
    liasse = client.get(f"/dossiers/{KARIM}/liasse-fiscale.pdf", headers=_en_tete(KARIM))
    assert liasse.status_code == 409
    assert "confirmer la forme juridique" in liasse.json()["detail"]
    cloture = client.get(f"/dossiers/{KARIM}/cloture-exercice", headers=_en_tete(KARIM)).json()
    assert cloture["possible"] is False
    assert cloture["code"] == "configuration"


def test_confirmer_en_choisissant_sasu_debloque_la_liasse() -> None:
    client = _client_a_confirmer()
    reponse = client.post(
        f"/dossiers/{KARIM}/configuration/confirmer",
        json={"forme_juridique": "SASU"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    assert (reponse.json()["forme_juridique"], reponse.json()["raison_blocage"]) == ("SASU", None)
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    assert [c[0] for c in depot.confirmations] == [KARIM]
    # La clôture peut encore attendre autre chose, plus la configuration.
    cloture = client.get(f"/dossiers/{KARIM}/cloture-exercice", headers=_en_tete(KARIM)).json()
    assert cloture.get("code") != "configuration"


def test_une_forme_hors_de_la_paire_est_refusee() -> None:
    reponse = _client_a_confirmer().post(
        f"/dossiers/{KARIM}/configuration/confirmer",
        json={"forme_juridique": "EURL"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 422


def test_un_autre_chauffeur_ne_confirme_pas_ce_dossier() -> None:
    reponse = _client_a_confirmer().post(
        f"/dossiers/{KARIM}/configuration/confirmer", json={}, headers=_en_tete("DEMO_sophie")
    )
    assert reponse.status_code in (403, 404)
