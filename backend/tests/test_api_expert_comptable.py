"""AXE-800 : l'expert-comptable prend la responsabilité juridique de ses changements."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.routes import get_experts, get_services_rollee, get_settlements
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire
from axelcompta.plateformes_rollee import ServicesRollee
from axelcompta.workflow.expert_comptable import (
    ROLE_EXPERT,
    TEXTE_ENGAGEMENT,
    VERSION_ENGAGEMENT,
    ExpertMemoire,
)
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _client_expert,
    _en_tete,
    _en_tete_gestionnaire,
    _expert_habilite,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()


def _experts(client: TestClient) -> ExpertMemoire:
    experts = client.app.dependency_overrides[get_experts]()  # type: ignore[attr-defined]
    assert isinstance(experts, ExpertMemoire)
    return experts


def _une_operation_a_imputer(client: TestClient) -> dict[str, str]:
    sujets = client.get("/expert/file", headers=EN_TETE).json()["sujets"]
    return next(s for s in sujets if s["dossier_id"] == "DEMO_sophie" and s["imputable"])


def _imputer(client: TestClient, ecriture_id: str, motif: str = "Plein de la flotte") -> int:
    reponse = client.post(
        "/expert/imputations",
        json={
            "dossier_id": "DEMO_sophie",
            "ecriture_id": ecriture_id,
            "compte": "6061",
            "motif": motif,
        },
        headers=EN_TETE,
    )
    return int(reponse.status_code)


def test_un_admin_sans_role_expert_ne_voit_pas_le_detail_et_n_impute_pas() -> None:
    admin = _client_et_stubs(role="admin")[0]
    assert admin.get("/expert/file", headers=EN_TETE).status_code == 403
    assert _imputer(admin, "DEMO_sophie:x") == 403
    assert admin.get("/dossiers/DEMO_sophie/anomalies", headers=EN_TETE).status_code == 403
    # Les agrégats restent au gestionnaire (doc 19 §2.1).
    assert admin.get("/dossiers", headers=EN_TETE).status_code == 200


def test_sans_engagement_l_expert_est_refuse_puis_impute_une_fois_engage() -> None:
    client = _client_et_stubs(role=ROLE_EXPERT)[0]
    experts = _experts(client)
    experts.habilitations.clear()
    experts.engagements.clear()
    _expert_habilite(experts)
    experts.engagements.clear()  # habilité, pas encore engagé

    refus = client.get("/expert/file", headers=EN_TETE)
    assert refus.status_code == 403
    assert "engagement" in refus.json()["detail"]
    etat = client.get("/expert/engagement", headers=EN_TETE).json()
    assert (etat["accepte"], etat["texte"]) == (False, TEXTE_ENGAGEMENT)

    accepte = client.post(
        "/expert/engagement",
        json={"version": VERSION_ENGAGEMENT, "texte": TEXTE_ENGAGEMENT},
        headers=EN_TETE,
    )
    cible = _une_operation_a_imputer(client)

    assert accepte.status_code == 200
    assert _imputer(client, cible["ecriture_id"]) == 200
    (decision,) = experts.decisions(DossierId("DEMO_sophie"))
    assert (decision.nature, decision.motif, decision.auteur_nom) == (
        "imputation",
        "Plein de la flotte",
        "Claire Expert",
    )
    assert decision.version_engagement == VERSION_ENGAGEMENT
    assert len(decision.ecritures) >= 2  # contre-passation et nouvelle écriture (I6)
    (engagement,) = experts.engagements
    assert engagement.texte == TEXTE_ENGAGEMENT


def test_un_engagement_qui_n_est_pas_le_texte_presente_est_refuse() -> None:
    client = _client_expert()
    reponse = client.post(
        "/expert/engagement",
        json={"version": VERSION_ENGAGEMENT, "texte": "J'accepte."},
        headers=EN_TETE,
    )
    assert reponse.status_code == 422


def test_sans_motif_pas_d_imputation() -> None:
    client = _client_expert()
    cible = _une_operation_a_imputer(client)
    assert _imputer(client, cible["ecriture_id"], motif="  ") == 422
    assert _experts(client).decisions(DossierId("DEMO_sophie")) == ()


def test_l_expert_n_agit_pas_hors_de_sa_lettre_de_mission() -> None:
    client = _client_et_stubs(role=ROLE_EXPERT)[0]
    experts = _experts(client)
    experts.habilitations.clear()
    _expert_habilite(experts, dossiers=(DossierId("DEMO_karim"),))

    dossiers_de_la_file = {
        s["dossier_id"] for s in client.get("/expert/file", headers=EN_TETE).json()["sujets"]
    }
    anomalies = client.get("/dossiers/DEMO_sophie/anomalies", headers=EN_TETE)

    assert dossiers_de_la_file <= {"DEMO_karim"}
    assert anomalies.status_code == 403
    assert _imputer(client, "DEMO_sophie:x") == 403


def test_le_chauffeur_voit_qui_a_reclasse_son_operation_et_pourquoi() -> None:
    client = _client_expert()
    cible = _une_operation_a_imputer(client)
    assert _imputer(client, cible["ecriture_id"], motif="Facture de carburant fournie") == 200

    operations = client.get(
        "/dossiers/DEMO_sophie/transactions", headers=_en_tete("DEMO_sophie")
    ).json()

    reclassees = [o for o in operations if o["reclassee_par"]]
    assert reclassees
    assert reclassees[0]["reclassee_par"] == "Claire Expert, expert-comptable"
    assert reclassees[0]["motif_reclassement"] == "Facture de carburant fournie"


def test_un_admin_habilite_l_expert_sur_des_dossiers_de_son_portefeuille() -> None:
    admin = _client_et_stubs(role="admin")[0]
    corps = {
        "email": "Expert@Cabinet.fr",
        "nom": "Claire Expert",
        "cabinet": "Cabinet Exemple",
        "numero_ordre": "13-000001",
        "lettre_mission": "LM-2026-01",
        "date_lettre": date(2026, 1, 1).isoformat(),
        "dossiers": ["DEMO_karim"],
    }

    reponse = admin.post("/portefeuille/experts", json=corps, headers=EN_TETE)
    inconnu = admin.post(
        "/portefeuille/experts", json={**corps, "dossiers": ["AILLEURS"]}, headers=EN_TETE
    )
    incomplet = admin.post("/portefeuille/experts", json={**corps, "cabinet": " "}, headers=EN_TETE)
    membre = _client_et_stubs(role="membre")[0].post(
        "/portefeuille/experts", json=corps, headers=EN_TETE
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["email"] == "expert@cabinet.fr"
    assert (inconnu.status_code, incomplet.status_code, membre.status_code) == (404, 422, 403)


def test_un_taux_choisi_separe_la_tva_et_un_taux_inconnu_est_refuse() -> None:
    client = _client_expert()
    cible = _une_operation_a_imputer(client)
    refuse = client.post(
        "/expert/imputations",
        json={
            "dossier_id": "DEMO_sophie",
            "ecriture_id": cible["ecriture_id"],
            "compte": "6061",
            "motif": "Taux hors liste",
            "taux": "19.6",
        },
        headers=EN_TETE,
    )
    assert refuse.status_code == 422

    reponse = client.post(
        "/expert/imputations",
        json={
            "dossier_id": "DEMO_sophie",
            "ecriture_id": cible["ecriture_id"],
            "compte": "6061",
            "motif": "Carburant, TVA 20",
            "taux": "20",
        },
        headers=EN_TETE,
    )
    assert reponse.status_code == 200, reponse.text
    comptes = {ligne["compte"] for ligne in reponse.json()["lignes"]}
    assert {"512", "6061", "44566"} <= comptes


def test_un_taux_global_reapparait_sur_la_ligne() -> None:
    client = _client_expert()
    file = client.get("/expert/file", headers=EN_TETE).json()
    assert file["chauffeurs"]
    sujet = next(s for s in file["sujets"] if s["dossier_id"] == "DEMO_sophie" and s["ecriture_id"])
    pose = client.post(
        "/expert/taux",
        json={
            "dossier_id": sujet["dossier_id"],
            "ecriture_id": sujet["ecriture_id"],
            "libelle": sujet["libelle"],
            "taux": "10",
            "portee": "global",
        },
        headers=EN_TETE,
    )
    assert pose.status_code == 204, pose.text
    sujets = client.get("/expert/file", headers=EN_TETE).json()["sujets"]
    relu = next(s for s in sujets if s["id"] == sujet["id"])
    assert (relu["taux_tva"], relu["origine_taux"]) == ("10", "appris")


def test_l_expert_ajoute_et_relit_un_ticket() -> None:
    client = _client_expert()
    sujet = _une_operation_a_imputer(client)
    chemin = f"/expert/dossiers/DEMO_sophie/ecritures/{sujet['ecriture_id']}/justificatif"
    assert client.get(chemin, headers=EN_TETE).status_code == 404
    pose = client.post(
        chemin,
        files={"fichier": ("ticket.jpg", b"\xff\xd8\xff ticket", "image/jpeg")},
        headers=EN_TETE,
    )
    assert pose.status_code == 204, pose.text
    lu = client.get(chemin, headers=EN_TETE)
    assert lu.status_code == 200
    assert lu.content.startswith(b"\xff\xd8")
    ligne = next(
        s
        for s in client.get("/expert/file", headers=EN_TETE).json()["sujets"]
        if s["ecriture_id"] == sujet["ecriture_id"]
    )
    assert ligne["a_justificatif"] is True


def test_l_expert_lit_les_rapprochements_rollee_de_son_dossier() -> None:
    client = _client_expert()
    cast(FastAPI, client.app).dependency_overrides[get_settlements] = lambda: SettlementsMemoire()
    reponse = client.get("/expert/dossiers/DEMO_sophie/rapprochements", headers=EN_TETE)
    assert reponse.status_code == 200
    assert isinstance(reponse.json(), list)


def test_sans_role_expert_les_rapprochements_sont_refuses() -> None:
    admin = _client_et_stubs(role="admin")[0]
    cast(FastAPI, admin.app).dependency_overrides[get_settlements] = lambda: SettlementsMemoire()
    refus = admin.get("/expert/dossiers/DEMO_sophie/rapprochements", headers=EN_TETE)
    assert refus.status_code == 403


def test_l_expert_lit_ce_qui_manque_meme_sans_rollee_ni_banque() -> None:
    """AXE-934 : sans compte Rollee relié, l'écran le dit ; les virements de
    plateforme déjà en banque sont signalés."""
    client = _client_expert()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_settlements] = lambda: SettlementsMemoire()
    services = ServicesRollee(cast(Any, None), ComptesRolleeMemoire())
    app.dependency_overrides[get_services_rollee] = lambda: services
    reponse = client.get("/expert/dossiers/DEMO_sophie/rapprochements/manques", headers=EN_TETE)
    assert reponse.status_code == 200, reponse.text
    premier, *suite = reponse.json()["manques"]
    assert premier == "Aucun compte Rollee n'est relié à cette entreprise : rien à rapprocher."
    assert all("aucun jour Rollee" in phrase for phrase in suite)  # virements de la démo
