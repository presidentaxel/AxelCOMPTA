"""AXE-808 : brancher l'e-mail du gestionnaire, se désinscrire, suivre les envois."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_api import get_envois
from axelcompta.workflow.rappels_envoi import (
    EnvoisMemoire,
    envois_du_rappel,
    lien_desinscription,
)
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

SMTP = {
    "fournisseur": "smtp",
    "parametres": {
        "hote": "smtp.serenity.fr",
        "port": "587",
        "utilisateur": "rappels",
        "mot_de_passe": "tres-secret",
        "expediteur": "rappels@serenity.fr",
    },
}


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _client(role: str = "admin") -> tuple[TestClient, EnvoisMemoire]:
    client = _client_et_stubs(role=role)[0]
    depot = EnvoisMemoire()
    client.app.dependency_overrides[get_envois] = lambda: depot  # type: ignore[attr-defined]
    return client, depot


def test_l_admin_branche_son_smtp_et_le_secret_ne_revient_jamais() -> None:
    client, depot = _client()
    reponse = client.put(
        "/portefeuille/integrations/envoi/mail", json=SMTP, headers=_en_tete_gestionnaire()
    )
    lue = client.get("/portefeuille/integrations/envoi", headers=_en_tete_gestionnaire())
    assert reponse.status_code == 200, reponse.text
    assert "mail" in lue.json()["canaux"]
    assert "tres-secret" not in reponse.text + lue.text
    integration = depot.integration(TenantId("TENANT_DEMO"), "mail")
    assert integration is not None and "tres-secret" not in integration.parametres_chiffres


def test_seul_l_admin_branche_et_un_champ_manquant_est_refuse() -> None:
    membre, _ = _client(role="membre")
    assert (
        membre.put(
            "/portefeuille/integrations/envoi/mail", json=SMTP, headers=_en_tete_gestionnaire()
        ).status_code
        == 403
    )
    admin, _ = _client()
    incomplet = {"fournisseur": "smtp", "parametres": {"hote": "x"}}
    assert (
        admin.put(
            "/portefeuille/integrations/envoi/mail", json=incomplet, headers=_en_tete_gestionnaire()
        ).status_code
        == 422
    )


def test_le_lien_de_desinscription_marche_sans_compte_et_seulement_signe() -> None:
    client, depot = _client()
    lien = lien_desinscription("", DossierId("DEMO_karim"), "mail")
    bon = client.get(lien)
    faux = client.get("/desinscription?d=DEMO_karim&c=mail&j=0000")
    assert bon.status_code == 200 and "plus de rappels par e-mail" in bon.json()["message"]
    assert faux.status_code == 404
    assert depot.stop == {("DEMO_karim", "mail")}


def test_le_gestionnaire_suit_les_envois_d_une_entreprise_sans_leur_contenu() -> None:
    client, depot = _client()
    depot.creer(
        envois_du_rappel(
            "r1",
            TenantId("TENANT_DEMO"),
            DossierId("DEMO_karim"),
            "Message",
            ["mail"],
            ["mail"],
            datetime(2026, 11, 9),
        )
    )
    suivi = client.get("/dossiers/DEMO_karim/envois", headers=_en_tete_gestionnaire()).json()
    assert [(e["canal"], e["statut"]) for e in suivi] == [("mail", "en_attente")]
    assert "message" not in suivi[0]
