"""AXE-822 : le compte de test ouvre l'espace chauffeur de n'importe quel
dossier de son portefeuille, en lecture seule, jusqu'à sa date de fin."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_api import get_consultations, get_dossiers
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.workflow.consultations import JournalConsultationsMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _CLE_PRIVEE_TEST,
    _client,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

DEMAIN = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()


def _jeton_test(
    expire_le: str = DEMAIN, role: str = "lecteur_tous_dossiers", aal: str = "aal2"
) -> str:
    charge_utile = {
        "sub": "louis-test",
        "email": "test@axelcompta.fr",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "aal": aal,
        "app_metadata": {"role_test": role, "tenant_id": "TENANT_DEMO", "expire_le": expire_le},
    }
    return jwt.encode(charge_utile, _CLE_PRIVEE_TEST, algorithm="ES256")


def _en_tete_test(dossier_id: str | None = None, **options: str) -> dict[str, str]:
    en_tete = {"Authorization": f"Bearer {_jeton_test(**options)}"}
    if dossier_id is not None:
        en_tete["X-Dossier"] = dossier_id
    return en_tete


def _journal(client: TestClient) -> JournalConsultationsMemoire:
    journal: JournalConsultationsMemoire = client.app.dependency_overrides[get_consultations]()  # type: ignore[attr-defined]
    return journal


def test_le_compte_de_test_passe_d_un_dossier_a_l_autre_et_chaque_ouverture_est_tracee() -> None:
    client = _client()

    choix = client.get("/lecteur-test/dossiers", headers=_en_tete_test())
    karim = client.get("/dossiers/DEMO_karim", headers=_en_tete_test("DEMO_karim"))
    sophie = client.get("/dossiers/DEMO_sophie", headers=_en_tete_test("DEMO_sophie"))
    operations = client.get(
        "/dossiers/DEMO_sophie/transactions", headers=_en_tete_test("DEMO_sophie")
    )

    assert choix.status_code == 200
    assert {"DEMO_karim", "DEMO_sophie"} <= {d["dossier_id"] for d in choix.json()}
    assert all(d["nb_operations"] >= 0 for d in choix.json())
    assert (karim.status_code, sophie.status_code, operations.status_code) == (200, 200, 200)
    assert [(str(d), str(a)) for d, a, _le in _journal(client).lignes] == [
        ("DEMO_karim", "louis-test"),
        ("DEMO_sophie", "louis-test"),
    ]


def test_le_compte_de_test_ne_peut_rien_ecrire() -> None:
    client = _client()
    reponse = client.post(
        "/dossiers/DEMO_karim/transactions/x/decision",
        json={"categorie": "carburant"},
        headers=_en_tete_test("DEMO_karim"),
    )
    assert reponse.status_code == 403
    assert reponse.json()["detail"] == "Compte de test : lecture seule."


def test_le_dossier_demande_doit_etre_celui_de_l_en_tete() -> None:
    client = _client()
    reponse = client.get("/dossiers/DEMO_sophie", headers=_en_tete_test("DEMO_karim"))
    assert reponse.status_code == 403
    sans_choix = client.get("/dossiers/DEMO_sophie", headers=_en_tete_test())
    assert sans_choix.status_code == 403


def test_un_dossier_d_un_autre_portefeuille_est_refuse() -> None:
    client = _client()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    depot.enregistrer_tenant(Tenant(id=TenantId("AUTRE"), nom="Autre"))
    depot.enregistrer(
        Dossier(
            id=DossierId("AUTRE_1"),
            tenant_id=TenantId("AUTRE"),
            forme_juridique="SASU",
            regime_imposition="IS",
            regime_tva="franchise",
            nom="Ailleurs",
            tva_recettes_regime="franchise",
            exercice_debut=date(2026, 1, 1),
        )
    )

    reponse = client.get("/dossiers/AUTRE_1", headers=_en_tete_test("AUTRE_1"))

    assert reponse.status_code == 403
    noms = {
        d["dossier_id"]
        for d in client.get("/lecteur-test/dossiers", headers=_en_tete_test()).json()
    }
    assert "AUTRE_1" not in noms


def test_un_chauffeur_ne_peut_pas_utiliser_x_dossier() -> None:
    """L'en-tête n'est lu que pour le compte de test : ailleurs, il est ignoré."""
    client = _client()
    en_tete = {**_en_tete("DEMO_karim"), "X-Dossier": "DEMO_sophie"}
    assert client.get("/dossiers/DEMO_sophie", headers=en_tete).status_code == 403
    assert client.get("/dossiers/DEMO_karim", headers=en_tete).status_code == 200


def test_le_compte_de_test_n_ouvre_aucune_route_gestionnaire() -> None:
    client = _client()
    assert client.get("/dossiers", headers=_en_tete_test()).status_code == 403
    assert client.get("/expert/file", headers=_en_tete_test()).status_code == 403


def test_l_ecran_de_choix_est_reserve_au_compte_de_test() -> None:
    client = _client()
    assert client.get("/lecteur-test/dossiers").status_code == 401
    assert client.get("/lecteur-test/dossiers", headers=_en_tete("DEMO_karim")).status_code == 403
    gestionnaire = client.get("/lecteur-test/dossiers", headers=_en_tete_gestionnaire())
    assert gestionnaire.status_code == 403


def test_passe_la_date_de_fin_le_compte_ne_voit_plus_rien() -> None:
    client = _client()
    hier = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    reponse = client.get(
        "/dossiers/DEMO_karim", headers=_en_tete_test("DEMO_karim", expire_le=hier)
    )
    assert reponse.status_code == 401
    assert "expiré" in reponse.json()["detail"]


def test_un_role_de_test_inconnu_est_refuse() -> None:
    client = _client()
    reponse = client.get("/lecteur-test/dossiers", headers=_en_tete_test(role="admin_tous"))
    assert reponse.status_code == 401


def test_le_compte_de_test_sans_code_ne_lit_aucun_dossier() -> None:
    client = _client()
    reponse = client.get("/lecteur-test/dossiers", headers=_en_tete_test(aal="aal1"))
    assert reponse.status_code == 403
    assert reponse.json()["detail"] == "Activez la double authentification pour continuer."


def test_le_cote_gestionnaire_ouvre_le_portefeuille_une_fois_le_code_saisi() -> None:
    client = _client()
    sans_code = {**_en_tete_test(aal="aal1"), "X-Cote": "gestionnaire"}
    avec_code = {**_en_tete_test(), "X-Cote": "gestionnaire"}

    assert client.get("/dossiers", headers=sans_code).status_code == 403
    assert client.get("/portefeuille/moi", headers=sans_code).status_code == 200
    assert client.get("/dossiers", headers=avec_code).status_code == 200
    assert client.get("/dossiers", headers=_en_tete_test()).status_code == 403
