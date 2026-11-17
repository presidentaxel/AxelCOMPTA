"""AXE-941 : fiches d'import d'un chauffeur, de l'ouverture à la création du dossier."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from axelcompta.api.routes import (
    get_branchements,
    get_demandes_jobs,
    get_dossiers,
    get_fiches_import,
    get_lire_comptes_digifactory,
    get_lire_contacts_digifactory,
    get_lire_fiche_officielle,
    get_lire_premiere_ecriture_digifactory,
)
from axelcompta.core.ids import DossierId
from axelcompta.ingestion.comptes_bancaires import CompteDigifactory
from axelcompta.jobs.file import FileMemoire
from axelcompta.tenants.branchements import BranchementsMemoire
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
    depot = app.dependency_overrides[get_dossiers]()
    fiches = FichesImportMemoire(existe=lambda ident: depot.obtenir(DossierId(ident)) is not None)
    file = FileMemoire()
    app.dependency_overrides[get_fiches_import] = lambda: fiches
    app.dependency_overrides[get_demandes_jobs] = lambda: file
    lire = (lambda siren: OFFICIELLE if siren == SIREN else None) if registres else None
    app.dependency_overrides[get_lire_fiche_officielle] = lambda: lire
    branchements = BranchementsMemoire()
    app.dependency_overrides[get_branchements] = lambda: branchements
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
    assert (fiche["statut"], fiche["registre_sources"]) == ("en_traitement", ["insee", "rne"])
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
    assert complete.json()["statut"] == "en_traitement"  # calculé
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


def _emplacement(fiche: dict[str, Any], cle: str) -> dict[str, Any]:
    return dict(next(e for e in fiche["emplacements"] if e["cle"] == cle))


def test_deposer_a_son_emplacement_relire_et_retirer() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}/documents"

    depot = client.post(
        route,
        files={"fichier": ("liasse-2025.pdf", b"%PDF-1.4", "application/pdf")},
        data={"emplacement": "reprise:liasse:2025"},
        headers=EN_TETE,
    )
    refuse = client.post(
        route,
        files={"fichier": ("virus.exe", b"MZ", "application/octet-stream")},
        data={"emplacement": "documents:autre"},
        headers=EN_TETE,
    )
    (document,) = _emplacement(depot.json(), "reprise:liasse:2025")["documents"]
    relu = client.get(f"{route}/{document['id']}", headers=EN_TETE)
    retire = client.delete(f"{route}/{document['id']}", headers=EN_TETE)

    assert depot.status_code == 200
    assert (document["libelle"], document["statut_traitement"]) == ("Liasse fiscale", "a_traiter")
    assert depot.json()["documents_a_lire"] == 1
    assert refuse.status_code == 422
    assert relu.content == b"%PDF-1.4"
    assert _emplacement(retire.json(), "reprise:liasse:2025")["documents"] == []


def test_un_releve_qif_depose_est_lu_tout_de_suite() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    depot = client.post(
        f"/portefeuille/imports/{fiche['id']}/documents",
        files={
            "fichier": (
                "releve.qif",
                b"!Type:Bank\nD31/01/2026\nT-12,00\nPTotal\n^\n",
                "text/plain",
            )
        },
        data={"emplacement": "banque:releve_bancaire"},
        headers=EN_TETE,
    )
    (document,) = _emplacement(depot.json(), "banque:releve_bancaire")["documents"]
    assert document["statut_traitement"] == "traite"
    assert document["resume"].startswith("QIF lu : 1 opérations")


def test_une_fiche_complete_est_tout_de_suite_au_portefeuille() -> None:
    client, file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}"
    depot = cast(FastAPI, client.app).dependency_overrides[get_dossiers]()

    incomplet = client.post(f"{route}/chauffeur", headers=EN_TETE)
    complete = client.patch(
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
    encore = client.post(f"{route}/chauffeur", headers=EN_TETE)

    assert incomplet.status_code == 422 and "Imposition" in incomplet.json()["detail"]
    assert complete.status_code == 200, complete.text
    assert (complete.json()["dossier_id"], complete.json()["dossier_cree"]) == (
        f"SIREN_{SIREN}",
        True,
    )
    assert depot.obtenir(DossierId(f"SIREN_{SIREN}")).nom == "MK DRIVING"
    assert encore.status_code == 200 and encore.json()["dossier_cree"] is True
    assert file.dernier("TENANT_DEMO", "import_dossiers") is None


def test_ignorer_une_fiche_puis_la_remettre() -> None:
    client, _file = _client(registres=False)
    fiche = _ouvrir(client, siren="")
    route = f"/portefeuille/imports/{fiche['id']}"

    ignoree = client.post(f"{route}/ignorer", headers=EN_TETE)
    assert ignoree.status_code == 200, ignoree.text
    assert ignoree.json()["statut"] == "ignore"
    assert client.get("/portefeuille/imports", headers=EN_TETE).json()[0]["statut"] == "ignore"

    reprise = client.post(f"{route}/reprendre", headers=EN_TETE)
    assert reprise.status_code == 200, reprise.text
    assert reprise.json()["statut"] == "a_importer"


def test_annuler_un_import_le_sort_de_la_liste() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}"

    annule = client.post(f"{route}/annuler", headers=EN_TETE)

    assert annule.status_code == 204
    assert client.get("/portefeuille/imports", headers=EN_TETE).json() == []
    assert client.get(route, headers=EN_TETE).status_code == 404


def test_le_contact_digifactory_de_la_personne_et_sinon_pas_connecte() -> None:
    client, _file = _client()
    app = cast(FastAPI, client.app)
    contacts = {
        "22755": {"companyName": "MK DRIVING", "siret": "55210055400013"},
        "9": {"companyName": "AUTRE"},
    }
    app.dependency_overrides[get_lire_contacts_digifactory] = lambda: lambda _b: contacts
    fiche = _ouvrir(client)
    trouve = client.get(f"/portefeuille/imports/{fiche['id']}/digifactory", headers=EN_TETE).json()

    def en_panne(_b: object) -> dict[str, dict[str, object]]:
        raise RuntimeError("Digifactory injoignable")

    app.dependency_overrides[get_lire_contacts_digifactory] = lambda: en_panne
    panne = client.get(f"/portefeuille/imports/{fiche['id']}/digifactory", headers=EN_TETE).json()

    assert trouve["lu"] is True
    assert [(c["contact_nr"], c["a_un_dossier"]) for c in trouve["contacts"]] == [("22755", False)]
    assert panne == {"lu": False, "contacts": []}


def test_l_historique_bancaire_est_la_premiere_ecriture_digifactory() -> None:
    client, _file = _client()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_lire_premiere_ecriture_digifactory] = lambda: (
        lambda _branchements, contact: date(2024, 3, 2) if contact == "22755" else None
    )
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}/digifactory/22755/historique"

    trouve = client.get(route, headers=EN_TETE)

    def en_panne(_branchements: object, _contact: str) -> date:
        raise RuntimeError("Digifactory injoignable")

    app.dependency_overrides[get_lire_premiere_ecriture_digifactory] = lambda: en_panne
    panne = client.get(route, headers=EN_TETE)

    assert trouve.json() == {"lu": True, "debut": "2024-03-02"}
    assert panne.json() == {"lu": False, "debut": None}


def test_les_comptes_digifactory_se_lisent_pour_choisir_pro_ou_perso() -> None:
    client, _file = _client()
    app = cast(FastAPI, client.app)
    courant = CompteDigifactory(
        "12", "Compte courant", "Qonto", "FR7630006000011234567890189", True
    )
    app.dependency_overrides[get_lire_comptes_digifactory] = lambda: (
        lambda _branchements, contact: (courant,) if contact == "22755" else ()
    )
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}/digifactory/22755/comptes"

    trouve = client.get(route, headers=EN_TETE)

    def en_panne(_branchements: object, _contact: str) -> tuple[CompteDigifactory, ...]:
        raise RuntimeError("Digifactory injoignable")

    app.dependency_overrides[get_lire_comptes_digifactory] = lambda: en_panne
    panne = client.get(route, headers=EN_TETE)

    assert trouve.json() == {
        "lu": True,
        "comptes": [
            {
                "id": "12",
                "nom": "Compte courant",
                "banque": "Qonto",
                "iban": "FR7630006000011234567890189",
                "professionnel": True,
            }
        ],
    }
    assert panne.json() == {"lu": False, "comptes": []}


def test_saisir_un_siret_lance_seul_la_recherche_aux_registres() -> None:
    """AXE-946 : « SIREN ou SIRET » ; la fiche se remplit sans autre clic."""
    client, _file = _client()
    fiche = _ouvrir(client, siren="")

    reponse = client.patch(
        f"/portefeuille/imports/{fiche['id']}",
        json={"champs": {"siren": "552 100 554 00013"}},
        headers=EN_TETE,
    )

    entreprise = {c["cle"]: c["valeur"] for c in _section(reponse.json(), "entreprise")["champs"]}
    assert (entreprise["siren"], entreprise["siret"]) == (SIREN, "55210055400013")
    assert entreprise["denomination"] == "MK DRIVING"
    assert reponse.json()["registre_sources"] == ["insee", "rne"]


def test_la_fiche_dit_quels_champs_viennent_encore_du_registre() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    assert "denomination" in fiche["depuis_registre"]
    modifiee = client.patch(
        f"/portefeuille/imports/{fiche['id']}",
        json={"champs": {"denomination": "MK DRIVING VTC"}},
        headers=EN_TETE,
    ).json()
    assert "denomination" not in modifiee["depuis_registre"]


def test_le_navigateur_peut_supprimer() -> None:
    """AXE-948 : le contrôle préalable (CORS) acceptait GET, POST, PUT et
    PATCH, pas DELETE ; retirer un document échouait avant même l'appel."""
    client, _file = _client()
    for methode in ("DELETE", "PATCH"):
        reponse = client.options(
            "/portefeuille/imports/f/documents/d",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": methode,
            },
        )
        assert reponse.status_code == 200, methode
        assert methode in reponse.headers["access-control-allow-methods"]


def test_renvoyer_le_meme_siren_relit_les_registres() -> None:
    """AXE-951 : « Relire les registres » renvoie le SIREN inchangé."""
    client, _file = _client()
    fiche = _ouvrir(client)
    route = f"/portefeuille/imports/{fiche['id']}"
    client.patch(route, json={"champs": {"denomination": ""}}, headers=EN_TETE)

    relue = client.patch(route, json={"champs": {"siren": SIREN}}, headers=EN_TETE).json()

    entreprise = {c["cle"]: c["valeur"] for c in _section(relue, "entreprise")["champs"]}
    assert entreprise["denomination"] == "MK DRIVING"


# --- AXE-970 : tout l'historique, exercice par exercice -----------------------

FEC_2019 = (
    b"JournalCode\tEcritureNum\tEcritureDate\tCompteNum\tPieceRef\tEcritureLib"
    b"\tDebit\tCredit\tValidDate\r\n"
    b"BQ\t1\t20190105\t512000\tP1\tApport\t1000,00\t0,00\t20190105\r\n"
    b"BQ\t1\t20190105\t101000\tP1\tApport\t0,00\t1000,00\t20190105\r\n"
)


def _archive_2019() -> bytes:
    import io
    import zipfile

    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("55210055400010FEC20191231.csv", FEC_2019)
        archive.writestr("Grand Livre.pdf", b"%PDF-1.4")
        archive.writestr("Encaissements de Vente/ENC-001.pdf", b"%PDF-1.4")
        archive.writestr("META-INF/signature.pkcs7", b"sig")
    return tampon.getvalue()


def _deposer_2019(client: TestClient, fiche: dict[str, Any]) -> Any:
    return client.post(
        f"/portefeuille/imports/{fiche['id']}/exercices/2019/documents",
        files=[
            ("fichiers", ("archive-2019.zip", _archive_2019(), "application/zip")),
            ("fichiers", ("Synthèse de la déclaration tva.pdf", b"%PDF-1.4", "application/pdf")),
        ],
        headers=EN_TETE,
    )


def test_deposer_en_vrac_sur_un_exercice_ancien_classe_et_deplie() -> None:
    """2019, avant la création connue (2023) : l'exercice s'ajoute, l'archive
    reste intacte, chaque fichier qu'elle contient est rangé et le FEC lu."""
    client, _file = _client()
    fiche = _ouvrir(client)
    reponse = _deposer_2019(client, fiche)
    assert reponse.status_code == 200, reponse.text
    vue = reponse.json()

    assert 2019 in [e["annee"] for e in vue["exercices"]]
    (archive,) = _emplacement(vue, "reprise:archive:2019")["documents"]
    (fec,) = _emplacement(vue, "reprise:fec:2019")["documents"]
    assert archive["resume"] == "Archive gardée intacte : 3 fichier(s) rangé(s) à part."
    assert fec["origine_id"] == archive["id"]
    assert fec["statut_traitement"] == "traite"
    assert "Clos le 31/12/2019" in fec["resume"]
    assert len(_emplacement(vue, "reprise:grand_livre:2019")["documents"]) == 1
    assert len(_emplacement(vue, "reprise:piece:2019")["documents"]) == 1
    assert len(_emplacement(vue, "reprise:declaration_tva:2019")["documents"]) == 1
    assert _emplacement(vue, "reprise:piece:2019")["libelle"] == "Pièces justificatives 2019"


def test_un_document_classe_seul_se_reclasse() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    vue = _deposer_2019(client, fiche).json()
    (tva,) = _emplacement(vue, "reprise:declaration_tva:2019")["documents"]
    route = f"/portefeuille/imports/{fiche['id']}/documents/{tva['id']}"

    deplace = client.patch(route, json={"emplacement": "reprise:liasse:2018"}, headers=EN_TETE)
    refuse = client.patch(route, json={"emplacement": "reprise:liasse:1990"}, headers=EN_TETE)

    assert deplace.status_code == 200, deplace.text
    (liasse,) = _emplacement(deplace.json(), "reprise:liasse:2018")["documents"]
    assert liasse["id"] == tva["id"]
    assert 2018 in [e["annee"] for e in deplace.json()["exercices"]]
    assert refuse.status_code == 422


def test_retirer_une_archive_retire_ses_fichiers() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    vue = _deposer_2019(client, fiche).json()
    (archive,) = _emplacement(vue, "reprise:archive:2019")["documents"]
    retire = client.delete(
        f"/portefeuille/imports/{fiche['id']}/documents/{archive['id']}", headers=EN_TETE
    )
    restants = [d for e in retire.json()["emplacements"] for d in e["documents"]]
    assert [d["libelle"] for d in restants] == ["Déclarations de TVA"]


def test_un_lecteur_ne_depose_rien_sur_un_exercice() -> None:
    client, _file = _client()
    fiche = _ouvrir(client)
    lecteur = _client(role="lecture")[0]
    reponse = lecteur.post(
        f"/portefeuille/imports/{fiche['id']}/exercices/2019/documents",
        files=[("fichiers", ("a.pdf", b"%PDF", "application/pdf"))],
        headers=EN_TETE,
    )
    assert reponse.status_code == 403
