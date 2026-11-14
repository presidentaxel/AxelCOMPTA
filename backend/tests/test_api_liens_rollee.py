"""AXE-911 : le gestionnaire choisit, voit et corrige le lien Rollee d'un chauffeur."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import cast

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.routes import (
    get_annuaire_rollee,
    get_branchements,
    get_journal_acces,
    get_ledger,
    get_liens_rollee,
    get_services_rollee,
    get_settlements,
)
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.ingestion.annuaire_rollee import AnnuaireRolleeMemoire, FicheAnnuaire
from axelcompta.ingestion.comptes_rollee import CompteRelie, ComptesRolleeMemoire
from axelcompta.ingestion.liens_rollee import AChoisir, Lien, LiensRolleeMemoire
from axelcompta.ingestion.rapprochement_rollee import Apercu, Candidat
from axelcompta.ingestion.settlements_plateforme import SettlementsMemoire
from axelcompta.plateformes_rollee import ServicesRollee
from axelcompta.revenus_rollee import rapprocher
from axelcompta.tenants.branchements import BranchementsMemoire, nouveau
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)
from tests.test_revenus_rollee import DOSSIER, SEMAINE, _stocke, _virement

T = TenantId("TENANT_DEMO")
KARIM = DossierId("DEMO_karim")
LE = datetime(2026, 11, 13, 9, tzinfo=UTC)


def _monter(role: str = "admin") -> tuple[TestClient, LiensRolleeMemoire, SettlementsMemoire]:
    client = _client_et_stubs(role)[0]
    app = cast(FastAPI, client.app)
    liens = LiensRolleeMemoire(tenants={"DEMO_karim": T, "DEMO_sophie": T})
    attente = AChoisir(
        "u-9",
        T,
        "b1",
        "a_choisir",
        (
            Candidat("DEMO_karim", ("même nom",), False),
            Candidat("DEMO_sophie", ("même nom",), False),
        ),
        Apercu("K.B.", ("Uber",), "0189"),
        LE,
    )
    liens.remplacer_a_choisir(T, "b1", [attente])
    app.dependency_overrides[get_liens_rollee] = lambda: liens
    settlements = SettlementsMemoire()
    app.dependency_overrides[get_settlements] = lambda: settlements
    services = ServicesRollee(BranchementsMemoire(), ComptesRolleeMemoire())
    app.dependency_overrides[get_services_rollee] = lambda: services
    return client, liens, settlements


def test_le_portefeuille_montre_les_comptes_a_choisir_sans_rien_en_clair() -> None:
    client, _liens, _s = _monter()
    reponse = client.get("/portefeuille/rollee", headers=_en_tete_gestionnaire())
    assert reponse.status_code == 200
    corps = reponse.json()
    (attente,) = corps["a_choisir"]
    assert (attente["initiales"], attente["iban_fin"]) == ("K.B.", "0189")
    assert [c["dossier_id"] for c in attente["candidats"]] == ["DEMO_karim", "DEMO_sophie"]
    assert corps["etats"]["DEMO_karim"] == "a_choisir"
    assert corps["etats"]["DEMO_yanis"] == "non_relie"


def test_choisir_pose_un_lien_manuel_et_le_note_au_journal() -> None:
    client, liens, _s = _monter()
    reponse = client.post(
        "/portefeuille/rollee/choix",
        json={"rollee_user_id": "u-9", "dossier_id": "DEMO_karim"},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 204
    lien = liens.lien(KARIM)
    assert lien is not None and lien.origine == "manuel"
    assert liens.a_choisir(T) == []
    fiche = client.get("/dossiers/DEMO_karim/rollee", headers=_en_tete_gestionnaire()).json()
    assert fiche["lien"]["comment"].startswith("choisi par ")
    journal = cast(FastAPI, client.app).dependency_overrides[get_journal_acces]()
    assert [acte.type_acte for _d, acte in journal.actes] == ["lien_rollee"]


def test_aucun_de_ces_comptes_ecarte_le_user() -> None:
    client, liens, _s = _monter()
    reponse = client.post(
        "/portefeuille/rollee/choix",
        json={"rollee_user_id": "u-9", "dossier_id": None},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 204
    assert [a.etat for a in liens.a_choisir(T)] == ["ecarte"]
    vue = client.get("/portefeuille/rollee", headers=_en_tete_gestionnaire()).json()
    assert vue["a_choisir"] == []


def test_un_dossier_deja_relie_refuse_un_second_lien() -> None:
    client, liens, _s = _monter()
    liens.lier(Lien(KARIM, "u-1", "b1", "auto", LE, "iban"))
    reponse = client.post(
        "/portefeuille/rollee/choix",
        json={"rollee_user_id": "u-9", "dossier_id": "DEMO_karim"},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 409


def test_la_lecture_seule_ne_relie_rien_et_le_chauffeur_ne_voit_pas_la_file() -> None:
    client, _liens, _s = _monter(role="lecture")
    reponse = client.post(
        "/portefeuille/rollee/choix",
        json={"rollee_user_id": "u-9", "dossier_id": "DEMO_karim"},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 403
    assert client.get("/portefeuille/rollee", headers=_en_tete("DEMO_karim")).status_code in (
        401,
        403,
    )


def test_delier_contre_passe_les_ventilations_et_garde_l_historique() -> None:
    client, liens, settlements = _monter()
    app = cast(FastAPI, client.app)
    liens.lier(Lien(KARIM, "u-1", "b1", "auto", LE, "nom_email"))
    comptes = ComptesRolleeMemoire()
    comptes.remplacer_comptes(KARIM, [CompteRelie("acc-uber", KARIM, "Uber", True, False, LE, LE)])
    app.dependency_overrides[get_services_rollee] = lambda: ServicesRollee(
        BranchementsMemoire(), comptes
    )
    semaine = replace(SEMAINE, dossier_id=KARIM)
    virement = replace(_virement("S1", 848_00), dossier_id=KARIM)
    resultat = rapprocher(
        [_stocke(semaine)], [virement], replace(DOSSIER, id=KARIM), (), date(2026, 11, 11), LE
    )
    ledger = app.dependency_overrides[get_ledger]()
    for ecriture in (virement, *resultat.ecritures):
        ledger.enregistrer(ecriture)
    settlements.enregistrer(resultat.stockes)

    fiche = client.get("/dossiers/DEMO_karim/rollee", headers=_en_tete_gestionnaire()).json()
    assert fiche["versements_a_contrepasser"] == 1
    reponse = client.post(
        "/dossiers/DEMO_karim/rollee/delier",
        json={"motif": "homonyme"},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 200 and reponse.json() == {"versements_contrepasses": 1}
    assert liens.lien(KARIM) is None and comptes.comptes(KARIM) == []
    assert [s.etat for s in settlements.lister(KARIM)] == ["delie"]
    fiche = client.get("/dossiers/DEMO_karim/rollee", headers=_en_tete_gestionnaire()).json()
    assert fiche["lien"] is None and fiche["historique"][0]["motif"] == "homonyme"


def test_delier_exige_un_motif() -> None:
    client, liens, _s = _monter()
    liens.lier(Lien(KARIM, "u-1", "b1", "auto", LE, "iban"))
    reponse = client.post(
        "/dossiers/DEMO_karim/rollee/delier", json={"motif": "  "}, headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 400


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les identifiants d'un branchement sont chiffrés (AXE-872)."""
    monkeypatch.setenv("AXELCOMPTA_CLE_INTEGRATIONS", Fernet.generate_key().decode())


def _annuaire(client: TestClient) -> tuple[AnnuaireRolleeMemoire, BranchementsMemoire]:
    """AXE-919 : deux users Rollee dans l'annuaire, sur le compte « Serenity »."""
    app = cast(FastAPI, client.app)
    branchements = BranchementsMemoire()
    compte = nouveau(
        [], T, "rollee", "rollee", "Serenity", {"jeton": "j", "environnement": "production"}
    )
    branchements.enregistrer([compte], "admin", LE)
    annuaire = AnnuaireRolleeMemoire()
    annuaire.remplacer(
        T,
        compte.id,
        [
            FicheAnnuaire(
                "u-karim", T, compte.id, "Karim Benali", ("uber.com-rev",), "k•••i@x.fr", LE
            ),
            FicheAnnuaire("u-anne", T, compte.id, "Anne Arnaud", ("bolt.eu-rev",), None, LE),
        ],
    )
    app.dependency_overrides[get_annuaire_rollee] = lambda: annuaire
    app.dependency_overrides[get_branchements] = lambda: branchements
    return annuaire, branchements


def test_chercher_un_compte_rollee_par_son_nom_et_le_relier() -> None:
    client, liens, _ = _monter()
    _annuaire(client)
    en_tete = _en_tete_gestionnaire()
    trouves = client.get("/portefeuille/rollee/annuaire?q=benali kar", headers=en_tete).json()
    assert trouves == [
        {
            "rollee_user_id": "u-karim",
            "nom": "Karim Benali",
            "plateformes": ["uber.com-rev"],
            "compte": "Serenity",
            "email_masque": "k•••i@x.fr",
            "relie_a": None,
        }
    ]
    assert client.get("/portefeuille/rollee/annuaire?q=k", headers=en_tete).json() == []
    reponse = client.post(
        "/dossiers/DEMO_karim/rollee/lier", json={"rollee_user_id": "u-karim"}, headers=en_tete
    )
    assert reponse.status_code == 204
    lien = liens.lien(KARIM)
    assert lien is not None and (lien.rollee_user_id, lien.origine) == ("u-karim", "manuel")
    (relie,) = client.get("/portefeuille/rollee/annuaire?q=karim", headers=en_tete).json()
    assert relie["relie_a"] is not None


def test_relier_depuis_l_annuaire_refuse_un_user_pris_ou_inconnu_et_la_lecture() -> None:
    client, liens, _ = _monter()
    _annuaire(client)
    en_tete = _en_tete_gestionnaire()
    liens.lier(Lien(DossierId("DEMO_sophie"), "u-anne", "b1", "manuel", LE, None, "marie"))
    pris = client.post(
        "/dossiers/DEMO_karim/rollee/lier", json={"rollee_user_id": "u-anne"}, headers=en_tete
    )
    assert pris.status_code == 409
    inconnu = client.post(
        "/dossiers/DEMO_karim/rollee/lier", json={"rollee_user_id": "u-x"}, headers=en_tete
    )
    assert inconnu.status_code == 404 and "Rapprocher Rollee" in inconnu.json()["detail"]
    lecture, _, _ = _monter("lecture")
    _annuaire(lecture)
    refuse = lecture.post(
        "/dossiers/DEMO_karim/rollee/lier", json={"rollee_user_id": "u-karim"}, headers=en_tete
    )
    assert refuse.status_code == 403
