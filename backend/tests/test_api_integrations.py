"""AXE-872 : plusieurs intégrations de chaque type, gérées par l'admin, et
le choix du branchement d'un dossier."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from axelcompta import demo_api
from axelcompta.demo_api import get_branchements
from axelcompta.tenants.branchements import BranchementsMemoire
from axelcompta.tester_branchement import Essai
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

SMTP = {
    "hote": "smtp.serenity.fr",
    "port": "587",
    "utilisateur": "rappels",
    "mot_de_passe": "tres-secret",
    "expediteur": "rappels@serenity.fr",
}


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AXELCOMPTA_CLE_INTEGRATIONS", "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="
    )


def _client(role: str = "admin") -> tuple[TestClient, BranchementsMemoire]:
    client = _client_et_stubs(role=role)[0]
    depot = BranchementsMemoire()
    client.app.dependency_overrides[get_branchements] = lambda: depot  # type: ignore[attr-defined]
    return client, depot


def _ajouter(client: TestClient, nom: str, type_: str = "mail") -> list[dict[str, object]]:
    corps = (
        {"type": "mail", "fournisseur": "smtp", "nom": nom, "parametres": SMTP}
        if type_ == "mail"
        else {
            "type": "digifactory",
            "fournisseur": "digifactory",
            "nom": nom,
            "parametres": {"jeton": "x" * 64},
        }
    )
    reponse = client.post("/portefeuille/integrations", json=corps, headers=_en_tete_gestionnaire())
    assert reponse.status_code == 200, reponse.text
    liste: list[dict[str, object]] = reponse.json()
    return liste


def _id(liste: list[dict[str, object]], nom: str) -> str:
    return str(next(b["id"] for b in liste if b["nom"] == nom))


def test_deux_smtp_actifs_un_seul_par_defaut_jamais_de_secret() -> None:
    """Critère : au moins deux branchements actifs du même type."""
    client, _depot = _client()
    _ajouter(client, "SMTP principal")
    liste = _ajouter(client, "SMTP agence Nord")
    _ajouter(client, "Digifactory compte 1", "digifactory")
    lue = client.get("/portefeuille/integrations", headers=_en_tete_gestionnaire())
    mails = [b for b in lue.json() if b["type"] == "mail"]
    assert [(b["nom"], b["par_defaut"], b["actif"]) for b in mails] == [
        ("SMTP agence Nord", False, True),
        ("SMTP principal", True, True),
    ]
    assert "tres-secret" not in lue.text and "x" * 64 not in lue.text
    assert len(liste) == 2


def test_l_admin_change_le_defaut_renomme_et_desactive() -> None:
    client, _depot = _client()
    _ajouter(client, "A")
    liste = _ajouter(client, "B")
    nord = _id(liste, "B")
    reponse = client.patch(
        f"/portefeuille/integrations/{nord}",
        json={"par_defaut": True, "nom": "SMTP Nord"},
        headers=_en_tete_gestionnaire(),
    )
    vues = {b["nom"]: b for b in reponse.json()}
    assert vues["SMTP Nord"]["par_defaut"] and not vues["A"]["par_defaut"]
    refus = client.patch(
        f"/portefeuille/integrations/{nord}",
        json={"actif": False},
        headers=_en_tete_gestionnaire(),
    )
    assert refus.status_code == 409


def test_seul_l_admin_gere_les_integrations_et_les_erreurs_sont_lisibles() -> None:
    membre, _ = _client(role="membre")
    refuse = membre.post(
        "/portefeuille/integrations",
        json={"type": "mail", "fournisseur": "smtp", "nom": "X", "parametres": SMTP},
        headers=_en_tete_gestionnaire(),
    )
    assert refuse.status_code == 403
    admin, _ = _client()
    incomplet = {"type": "mail", "fournisseur": "smtp", "nom": "X", "parametres": {"hote": "x"}}
    assert (
        admin.post(
            "/portefeuille/integrations", json=incomplet, headers=_en_tete_gestionnaire()
        ).status_code
        == 422
    )
    assert (
        admin.patch(
            "/portefeuille/integrations/inconnu", json={"nom": "x"}, headers=_en_tete_gestionnaire()
        ).status_code
        == 404
    )


def test_un_dossier_choisit_son_branchement_puis_revient_au_defaut() -> None:
    client, _depot = _client()
    _ajouter(client, "A")
    nord = _id(_ajouter(client, "Nord"), "Nord")
    banque = _id(_ajouter(client, "Digi", "digifactory"), "Digi")
    url = "/dossiers/DEMO_karim/integrations"
    choisi = client.put(
        f"{url}/mail", json={"branchement_id": nord}, headers=_en_tete_gestionnaire()
    )
    assert choisi.status_code == 200 and choisi.json()["choix"] == {"mail": nord}
    mauvais_type = client.put(
        f"{url}/mail", json={"branchement_id": banque}, headers=_en_tete_gestionnaire()
    )
    assert mauvais_type.status_code == 422
    retour = client.put(
        f"{url}/mail", json={"branchement_id": None}, headers=_en_tete_gestionnaire()
    )
    assert retour.json()["choix"] == {}
    assert client.get(url, headers=_en_tete_gestionnaire()).json()["choix"] == {}


def test_tester_un_branchement_ne_renvoie_qu_un_statut_et_un_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _depot = _client()
    branchement = _id(_ajouter(client, "A"), "A")
    vus: list[str] = []

    def faux_test(b: object) -> Essai:
        vus.append(getattr(b, "nom", ""))
        return Essai("ok", "Connexion et identifiants acceptés. Aucun e-mail envoyé.")

    monkeypatch.setattr(demo_api, "tester_branchement", faux_test)
    reponse = client.post(
        f"/portefeuille/integrations/{branchement}/tester", headers=_en_tete_gestionnaire()
    )
    assert reponse.json()["statut"] == "ok" and vus == ["A"]
