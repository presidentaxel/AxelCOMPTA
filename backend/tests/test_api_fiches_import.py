"""AXE-941 : fiches d'import d'un chauffeur, de l'ouverture à la création du dossier."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.routes import get_demandes_jobs, get_fiches_import, get_lire_fiche_officielle
from axelcompta.jobs.file import TYPE_IMPORT_DOSSIERS, FileMemoire
from axelcompta.tenants.fiches_import_depot import FichesImportMemoire
from axelcompta.tenants.registres import FicheOfficielle
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()
SIREN = "552100554"
OFFICIELLE = FicheOfficielle(
    siren=SIREN,
    lu_le=date(2026, 11, 16),
    sources=("insee", "rne"),
    denomination="MK DRIVING",
    forme_juridique="SASU",
    date_creation=date(2023, 3, 15),
    cloture="31/12",
)


def _client(role: str = "admin", registres: bool = True) -> tuple[TestClient, FileMemoire]:
    client = _client_et_stubs(role=role)[0]
    app = cast(FastAPI, client.app)
    fiches, file = FichesImportMemoire(), FileMemoire()
    app.dependency_overrides[get_fiches_import] = lambda: fiches
    app.dependency_overrides[get_demandes_jobs] = lambda: file
    lire = (lambda siren: OFFICIELLE if siren == SIREN else None) if registres else None
    app.dependency_overrides[get_lire_fiche_officielle] = lambda: lire
    return client, file


def _ouvrir(client: TestClient, siren: str = SIREN) -> dict[str, Any]:
    reponse = client.post(
        "/portefeuille/imports",
        json={"nom": "Dupont", "prenom": "Karim", "siren": siren},
        headers=EN_TETE,
    )
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def _section(fiche: dict[str, Any], cle: str) -> dict[str, Any]:
    return dict(next(s for s in fiche["sections_detail"] if s["cle"] == cle))


def test_ouvrir_une_fiche_avec_un_siren_preremplit_l_entreprise() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)

    entreprise = {c["cle"]: c["valeur"] for c in _section(fiche, "entreprise")["champs"]}
    assert (entreprise["denomination"], entreprise["cloture"]) == ("MK DRIVING", "31/12")
    assert (fiche["statut"], fiche["registre_sources"]) == ("a_importer", ["insee", "rne"])
    assert [e["annee"] for e in fiche["exercices"]] == [2024, 2025, 2026]
    liste = client.get("/portefeuille/imports", headers=EN_TETE).json()
    assert [(f["id"], f["denomination"]) for f in liste] == [(fiche["id"], "MK DRIVING")]


def test_completer_une_categorie_et_refuser_une_valeur_illisible() -> None:
    client, _file = _client(registres=False)
    fiche = _ouvrir(client, siren="")
    route = f"/portefeuille/imports/{fiche['id']}"

    complete = client.patch(route, json={"champs": {"email": "k@x.fr"}}, headers=EN_TETE)
    illisible = client.patch(route, json={"champs": {"cloture": "31/13"}}, headers=EN_TETE)
    sans_siren = client.post(f"{route}/registres", headers=EN_TETE)

    assert complete.status_code == 200
    assert complete.json()["statut"] == "en_traitement"
    assert illisible.status_code == 422 and "jour et mois" in illisible.json()["detail"]
    assert sans_siren.status_code == 503  # registres pas branchés


def test_un_lecteur_ne_modifie_pas_et_un_autre_portefeuille_ne_voit_rien() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    lecteur, _ = _client(role="lecture")

    autre = client.get(
        f"/portefeuille/imports/{fiche['id']}", headers=_en_tete_gestionnaire("AUTRE_TENANT")
    )
    refus = lecteur.post("/portefeuille/imports", json={"nom": "X"}, headers=EN_TETE)

    assert autre.status_code == 404
    assert refus.status_code == 403


def test_deposer_relire_et_retirer_un_document() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}/documents"

    depot = client.post(
        route,
        files={"fichier": ("liasse-2025.pdf", b"%PDF-1.4", "application/pdf")},
        data={"categorie": "liasse", "exercice": "2025"},
        headers=EN_TETE,
    )
    refuse = client.post(
        route,
        files={"fichier": ("virus.exe", b"MZ", "application/octet-stream")},
        data={"categorie": "autre"},
        headers=EN_TETE,
    )
    (document,) = depot.json()["documents"]
    relu = client.get(f"{route}/{document['id']}", headers=EN_TETE)
    retire = client.delete(f"{route}/{document['id']}", headers=EN_TETE)

    assert depot.status_code == 200 and document["libelle"] == "Liasse fiscale"
    piece = depot.json()["exercices"][1]["pieces"][0]
    assert (piece["categorie"], piece["recue"]) == ("liasse", True)
    assert refuse.status_code == 422
    assert relu.content == b"%PDF-1.4"
    assert retire.json()["documents"] == []


def test_creer_le_chauffeur_confie_le_dossier_au_worker() -> None:
    client, file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}"

    incomplet = client.post(f"{route}/chauffeur", headers=EN_TETE)
    client.patch(
        route,
        json={
            "champs": {
                "regime_imposition": "IS",
                "regime_tva": "reel_normal",
                "exercice_debut": "2026-01-01",
            }
        },
        headers=EN_TETE,
    )
    cree = client.post(f"{route}/chauffeur", headers=EN_TETE)

    assert incomplet.status_code == 422 and "Imposition" in incomplet.json()["detail"]
    assert cree.status_code == 200, cree.text
    assert (cree.json()["dossier_id"], cree.json()["dossier_cree"]) == (f"SIREN_{SIREN}", False)
    job = file.dernier("TENANT_DEMO", TYPE_IMPORT_DOSSIERS)
    assert job is not None and "MK DRIVING" in job.payload


def test_une_fiche_traitee_se_rouvre_pour_etre_modifiee() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}"

    client.post(f"{route}/statut", json={"statut": "traitee"}, headers=EN_TETE)
    bloquee = client.patch(route, json={"champs": {"email": "k@x.fr"}}, headers=EN_TETE)
    client.post(f"{route}/statut", json={"statut": "en_traitement"}, headers=EN_TETE)
    rouverte = client.patch(route, json={"champs": {"email": "k@x.fr"}}, headers=EN_TETE)

    assert bloquee.status_code == 422 and "traitée" in bloquee.json()["detail"]
    assert rouverte.status_code == 200
