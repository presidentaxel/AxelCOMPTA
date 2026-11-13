"""AXE-808 : brancher l'e-mail du gestionnaire, se désinscrire, suivre les envois."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from axelcompta.api.routes import get_branchements, get_envois
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.branchements import BranchementsMemoire
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
    branchements = BranchementsMemoire()
    client.app.dependency_overrides[get_branchements] = lambda: branchements  # type: ignore[attr-defined]
    return client, depot


def test_un_smtp_branche_apparait_dans_les_canaux_sans_son_secret() -> None:
    client, _depot = _client()
    ajout = client.post(
        "/portefeuille/integrations",
        json={"type": "mail", "nom": "E-mail", **SMTP},
        headers=_en_tete_gestionnaire(),
    )
    lue = client.get("/portefeuille/integrations/envoi", headers=_en_tete_gestionnaire())
    assert ajout.status_code == 200, ajout.text
    assert list(lue.json()["canaux"]) == ["mail"]
    assert "tres-secret" not in ajout.text + lue.text


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
