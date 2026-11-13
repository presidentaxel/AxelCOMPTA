"""AXE-809 : rapport ligne par ligne, puis création par le worker."""

from __future__ import annotations

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_demandes_jobs
from axelcompta.jobs.file import TYPE_IMPORT_DOSSIERS, FileMemoire
from axelcompta.tenants.import_dossiers import COLONNES
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()
VALIDE = "552100554;MK DRIVING;SASU;IS;reel_normal;;2026-01-01;2026-12-31;;"
FAUSSE = "123456789;FAUSSE;SASU;IR;reel_normal;;2026-01-01;;;"
FICHIER = (";".join(COLONNES) + "\n" + VALIDE + "\n" + FAUSSE + "\n").encode()


def _client(role: str = "admin") -> tuple[TestClient, FileMemoire]:
    client = _client_et_stubs(role=role)[0]
    file = FileMemoire()
    client.app.dependency_overrides[get_demandes_jobs] = lambda: file  # type: ignore[attr-defined]
    return client, file


def _deposer(client: TestClient, route: str) -> dict[str, object]:
    reponse = client.post(route, files={"fichier": ("d.csv", FICHIER, "text/csv")}, headers=EN_TETE)
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def test_le_rapport_ne_cree_rien_et_dit_chaque_erreur() -> None:
    client, file = _client()
    vue = _deposer(client, "/portefeuille/import-dossiers/rapport")
    assert (vue["a_creer"], vue["en_erreur"]) == (1, 1)
    lignes = vue["lignes"]
    assert isinstance(lignes, list) and lignes[1]["numero"] == 3
    assert any("SIREN invalide" in e for e in lignes[1]["erreurs"])
    assert file.dernier("TENANT_DEMO", TYPE_IMPORT_DOSSIERS) is None


def test_l_import_confie_les_lignes_valides_au_worker_une_fois() -> None:
    client, file = _client()
    vue = _deposer(client, "/portefeuille/import-dossiers")
    creation = vue["creation"]
    assert isinstance(creation, dict) and creation["statut"] == "en_attente"
    job = file.dernier("TENANT_DEMO", TYPE_IMPORT_DOSSIERS)
    assert job is not None and "MK DRIVING" in job.payload
    encore = client.post(
        "/portefeuille/import-dossiers",
        files={"fichier": ("d.csv", FICHIER, "text/csv")},
        headers=EN_TETE,
    )
    assert encore.status_code == 409


def test_seul_l_admin_importe_et_le_modele_se_telecharge() -> None:
    membre, _ = _client(role="membre")
    refus = membre.post(
        "/portefeuille/import-dossiers",
        files={"fichier": ("d.csv", FICHIER, "text/csv")},
        headers=EN_TETE,
    )
    modele = membre.get("/portefeuille/import-dossiers/modele.csv", headers=EN_TETE)
    assert refus.status_code == 403
    assert modele.status_code == 200 and modele.text.startswith("siren;nom;")
