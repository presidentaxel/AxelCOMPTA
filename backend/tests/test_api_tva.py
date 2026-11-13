"""AXE-805 : « Ma TVA » — CA3 de chaque période, déclaration, rappels."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_dossiers, get_signatures_inpi
from axelcompta.closing.tva_rappels import notifier_tva
from axelcompta.core.ids import DossierId, EcritureId
from axelcompta.core.money import Money
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.notifications import TYPE_TVA_J7, InMemoryNotificationRepository
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
    _ledger_du_client,
)

KARIM = "DEMO_karim"  # exercice 2025


def _url(suite: str = "") -> str:
    return f"/dossiers/{KARIM}/tva{suite}"


def _client_mensuel() -> TestClient:
    client = _client()
    ledger = _ledger_du_client(client)
    ledger.enregistrer(
        Ecriture(
            EcritureId("DEMO_karim:tva-r1"),
            DossierId(KARIM),
            Journal.BQ,
            date(2025, 3, 5),
            "Uber",
            None,
            (
                LigneEcriture("512", Sens.DEBIT, Money(110_000)),
                LigneEcriture("706", Sens.CREDIT, Money(100_000)),
                LigneEcriture("44571", Sens.CREDIT, Money(10_000)),
            ),
        )
    )
    ledger.enregistrer(
        Ecriture(
            EcritureId("DEMO_karim:tva-d1"),
            DossierId(KARIM),
            Journal.BQ,
            date(2025, 3, 8),
            "Total",
            None,
            (
                LigneEcriture("6061", Sens.DEBIT, Money(5_000)),
                LigneEcriture("44566", Sens.DEBIT, Money(1_000)),
                LigneEcriture("512", Sens.CREDIT, Money(6_000)),
            ),
        )
    )
    reponse = client.put(
        _url("/parametres"),
        json={"periodicite": "mensuelle", "jour_echeance": 19},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    return client


def _mars(vue: dict[str, Any]) -> dict[str, Any]:
    periodes: list[dict[str, Any]] = vue["periodes"]
    return next(p for p in periodes if p["cle"] == "2025-03")


def test_la_ca3_de_mars_est_preparee_avec_son_echeance() -> None:
    client = _client_mensuel()
    mars = _mars(client.get(_url(), headers=_en_tete(KARIM)).json())
    lignes = {ligne["numero"]: ligne["centimes"] for ligne in mars["lignes"] if ligne["numero"]}
    assert mars["echeance"] == "2025-04-19"
    assert (lignes["16"], lignes["20"], lignes["28"]) >= (10_000, 1_000, 0)
    assert mars["declaree"] is False


def test_declarer_passe_la_liquidation_et_garde_la_preuve() -> None:
    client = _client_mensuel()
    reponse = client.post(
        _url("/2025-03/declaration"), json={"deposee_le": "2025-04-15"}, headers=_en_tete(KARIM)
    )
    assert reponse.status_code == 200, reponse.text
    assert _mars(reponse.json())["declaree"] is True
    ids = {e.id for e in _ledger_du_client(client).grand_livre(DossierId(KARIM))}
    assert "DEMO_karim:tva-periode-2025-03" in ids
    signatures = client.app.dependency_overrides[get_signatures_inpi]()  # type: ignore[attr-defined]
    assert signatures.dernier(DossierId(KARIM), "tva_ca3_2025-03") is not None
    deux_fois = client.post(
        _url("/2025-03/declaration"), json={"deposee_le": "2025-04-15"}, headers=_en_tete(KARIM)
    )
    assert deux_fois.status_code == 409


def test_une_declaration_avant_la_fin_de_la_periode_est_refusee() -> None:
    client = _client_mensuel()
    reponse = client.post(
        _url("/2025-03/declaration"), json={"deposee_le": "2025-03-20"}, headers=_en_tete(KARIM)
    )
    assert reponse.status_code == 422


def test_des_parametres_illisibles_sont_refuses_et_le_gestionnaire_n_y_touche_pas() -> None:
    client = _client()
    mauvais = client.put(
        _url("/parametres"),
        json={"periodicite": "annuelle", "jour_echeance": 19},
        headers=_en_tete(KARIM),
    )
    gestionnaire = client.get(_url(), headers=_en_tete_gestionnaire())
    assert (mauvais.status_code, gestionnaire.status_code) == (422, 403)


def test_le_gestionnaire_voit_la_periode_a_declarer_sans_montant() -> None:
    client = _client_mensuel()
    vue = client.get("/dossiers", headers=_en_tete_gestionnaire()).json()
    karim = next(d for d in vue if d["dossier_id"] == KARIM)
    assert karim["tva_a_declarer"] == "2025-01"  # la plus ancienne non déclarée
    assert karim["tva_echeance"] == "2025-02-19"


def test_la_cloche_relance_a_j7_un_dossier_qui_n_a_pas_declare() -> None:
    client = _client_mensuel()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    karim = depot.obtenir(DossierId(KARIM))
    notifications = InMemoryNotificationRepository()
    declarees = {f"tva_ca3_2025-{m:02d}" for m in (1, 2)}

    j7 = notifier_tva(karim, declarees, notifications, datetime(2025, 4, 12, 8, 0))
    encore = notifier_tva(karim, declarees, notifications, datetime(2025, 4, 13, 8, 0))
    loin = notifier_tva(karim, declarees, InMemoryNotificationRepository(), datetime(2025, 4, 2))

    assert (j7.statut, j7.type) == ("creee", TYPE_TVA_J7)
    assert encore.statut == "deja_notifie"
    assert loin.statut == "rien_a_faire"
