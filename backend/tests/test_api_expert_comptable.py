"""AXE-800 : l'expert-comptable prend la responsabilité juridique de ses changements."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.routes import (
    get_ecrire_role,
    get_experts,
    get_journal_acces,
    get_ledger,
    get_lire_role,
    get_services_rollee,
    get_settlements,
)
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_rollee import ComptesRolleeMemoire
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire, fusionner
from axelcompta.plateformes_rollee import ServicesRollee
from axelcompta.workflow.audit import ACTE_SEMAINE_TRANCHEE
from axelcompta.workflow.expert_comptable import (
    ROLE_EXPERT,
    TEXTE_ENGAGEMENT,
    VERSION_ENGAGEMENT,
    ExpertMemoire,
)
from axelcompta.workflow.journal_acces import JournalAccesMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _client_expert,
    _en_tete,
    _en_tete_gestionnaire,
    _expert_habilite,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
from tests.test_revenus_rollee import JOUR

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


CORPS_EXPERT = {
    "nom": "Claire Expert",
    "cabinet": "Cabinet Exemple",
    "numero_ordre": "13-000001",
    "lettre_mission": "LM-2026-01",
    "date_lettre": date(2026, 1, 1).isoformat(),
    "dossiers": ["DEMO_sophie"],
}


def _admin_qui_note_les_roles(roles: dict[str, str]) -> tuple[TestClient, list[str]]:
    client = _client_et_stubs(role="admin")[0]
    ecrits: list[str] = []
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ecrire_role] = lambda: (
        lambda _tenant, email, role: ecrits.append(f"{email}:{role}")
    )
    app.dependency_overrides[get_lire_role] = lambda: lambda _tenant, email: roles.get(email)
    return client, ecrits


def test_un_admin_qui_se_declare_expert_garde_ses_droits_et_ouvre_le_mode_expert() -> None:
    """AXE-940 : déclaré expert, l'admin restait `expert_comptable` et ne
    pouvait plus inviter personne."""
    client, ecrits = _admin_qui_note_les_roles({})
    corps = {**CORPS_EXPERT, "email": "gestionnaire@example.com"}

    assert client.post("/portefeuille/experts", json=corps, headers=EN_TETE).status_code == 200
    assert client.get("/expert/file", headers=EN_TETE).status_code == 403  # pas encore engagé
    engage = client.post(
        "/expert/engagement",
        json={"version": VERSION_ENGAGEMENT, "texte": TEXTE_ENGAGEMENT},
        headers=EN_TETE,
    )

    assert ecrits == []
    assert engage.status_code == 200
    assert client.get("/expert/file", headers=EN_TETE).status_code == 200


def test_declarer_expert_un_autre_admin_ne_change_pas_son_role_un_membre_si() -> None:
    client, ecrits = _admin_qui_note_les_roles(
        {"associe@cabinet.fr": "admin", "salarie@cabinet.fr": "membre"}
    )
    for email in ("associe@cabinet.fr", "salarie@cabinet.fr", "nouveau@cabinet.fr"):
        reponse = client.post(
            "/portefeuille/experts", json={**CORPS_EXPERT, "email": email}, headers=EN_TETE
        )
        assert reponse.status_code == 200, reponse.text

    assert ecrits == [
        f"salarie@cabinet.fr:{ROLE_EXPERT}",
        f"nouveau@cabinet.fr:{ROLE_EXPERT}",
    ]


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


def test_l_equipe_voit_les_experts_declares_et_un_admin_modifie_leurs_dossiers() -> None:
    """AXE-945 : la déclaration en vigueur se relit pour être modifiée ; la
    nouvelle remplace l'ancienne, l'engagement déjà accepté reste."""
    client = _client_et_stubs(role=ROLE_EXPERT)[0]  # habilité sur 3 dossiers, engagé
    avant = client.get("/portefeuille/experts", headers=EN_TETE).json()

    admin, _ecrits = _admin_qui_note_les_roles({})
    admin.app.dependency_overrides[get_experts] = client.app.dependency_overrides[get_experts]  # type: ignore[attr-defined]
    corps = {**CORPS_EXPERT, "email": "gestionnaire@example.com", "dossiers": ["DEMO_karim"]}
    assert admin.post("/portefeuille/experts", json=corps, headers=EN_TETE).status_code == 200
    (apres,) = client.get("/portefeuille/experts", headers=EN_TETE).json()

    assert [(e["email"], len(e["dossiers"]), e["engagement_accepte"]) for e in avant] == [
        ("gestionnaire@example.com", 3, True)
    ]
    assert (apres["dossiers"], apres["engagement_accepte"]) == (["DEMO_karim"], True)
    assert client.get("/expert/file", headers=EN_TETE).status_code == 200


def _jour_de_sophie() -> tuple[SettlementsMemoire, str]:
    """Un jour Uber de Sophie (semaine du 05/10/2026) qui attend une décision."""
    jour = replace(JOUR, dossier_id=DossierId("DEMO_sophie"))
    stocke = fusionner(None, "acc-uber", jour, datetime(2026, 11, 20, tzinfo=UTC))
    assert stocke is not None
    settlements = SettlementsMemoire()
    settlements.enregistrer([replace(stocke, etat="a_verifier", motif="semaine du 05/10 : écart")])
    return settlements, stocke.id


def _decider_semaine(client: TestClient, decision: str, motif: str) -> Any:
    return client.post(
        "/expert/dossiers/DEMO_sophie/rapprochements/decision",
        json={"plateforme": "uber", "lundi": "2026-10-05", "decision": decision, "motif": motif},
        headers=EN_TETE,
    )


def test_l_expert_ecarte_une_semaine_a_verifier_et_c_est_trace() -> None:
    """AXE-912 : la semaine sort de « à vérifier », le motif va au journal."""
    client = _client_expert()
    app = cast(FastAPI, client.app)
    settlements, identifiant = _jour_de_sophie()
    app.dependency_overrides[get_settlements] = lambda: settlements
    reponse = _decider_semaine(client, "ecarter", "Jours du compte de flotte")
    assert reponse.status_code == 200, reponse.text
    assert "1 jour(s) écarté(s)" in reponse.json()["resume"]
    assert settlements.stockes[identifiant].etat == "delie"
    journal: JournalAccesMemoire = app.dependency_overrides[get_journal_acces]()
    assert [a.type_acte for _d, a in journal.actes] == [ACTE_SEMAINE_TRANCHEE]


def test_une_decision_de_semaine_demande_un_motif_et_un_expert() -> None:
    client = _client_expert()
    settlements, identifiant = _jour_de_sophie()
    cast(FastAPI, client.app).dependency_overrides[get_settlements] = lambda: settlements
    assert _decider_semaine(client, "ecarter", " ").status_code in (400, 422)
    admin = _client_et_stubs(role="admin")[0]
    cast(FastAPI, admin.app).dependency_overrides[get_settlements] = lambda: settlements
    assert _decider_semaine(admin, "ecarter", "Jours du compte de flotte").status_code == 403
    assert settlements.stockes[identifiant].etat == "a_verifier"


def test_une_semaine_sans_rien_a_trancher_est_refusee() -> None:
    client = _client_expert()
    cast(FastAPI, client.app).dependency_overrides[get_settlements] = lambda: SettlementsMemoire()
    reponse = _decider_semaine(client, "ecrire", "Écart accepté")
    assert 400 <= reponse.status_code < 500
    assert "Rien à trancher" in reponse.json()["detail"]


def test_l_expert_impute_l_ecart_d_une_semaine_en_un_clic() -> None:
    """AXE-969 : la semaine est écrite, puis son écart va au compte choisi."""
    client = _client_expert()
    app = cast(FastAPI, client.app)
    settlements, identifiant = _jour_de_sophie()
    app.dependency_overrides[get_settlements] = lambda: settlements
    reponse = client.post(
        "/expert/dossiers/DEMO_sophie/rapprochements/decision",
        json={
            "plateforme": "uber",
            "lundi": "2026-10-05",
            "decision": "imputer",
            "compte": "658",
            "motif": "Écart de règlement Uber",
        },
        headers=EN_TETE,
    )
    assert reponse.status_code == 200, reponse.text
    assert "imputé au 658" in reponse.json()["resume"]
    assert settlements.stockes[identifiant].etat == "reconcilie"
    ledger = app.dependency_overrides[get_ledger]()
    (od,) = [e for e in ledger.grand_livre(DossierId("DEMO_sophie")) if "imputation" in e.id]
    assert {x.compte for x in od.lignes} == {"658", "4671"}


def test_imputer_demande_un_compte_qui_convient() -> None:
    client = _client_expert()
    settlements, _identifiant = _jour_de_sophie()
    cast(FastAPI, client.app).dependency_overrides[get_settlements] = lambda: settlements
    corps = {"plateforme": "uber", "lundi": "2026-10-05", "decision": "imputer", "motif": "Écart"}
    url = "/expert/dossiers/DEMO_sophie/rapprochements/decision"
    assert client.post(url, json=corps, headers=EN_TETE).status_code == 422
    corps["compte"] = "758"  # un encore dû ne va pas en produit
    assert client.post(url, json=corps, headers=EN_TETE).status_code == 422
