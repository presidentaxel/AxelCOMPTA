"""AXE-943 : le passage OCR d'un portefeuille, sur une fiche en mémoire."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from axelcompta.core.ids import TenantId
from axelcompta.ocr.categories import Categorie
from axelcompta.ocr.lecture import HAIKU, SONNET, Appel
from axelcompta.ocr.passage import a_lire, media_type, passer
from axelcompta.tenants.fiches_import import document_import, nouvelle_fiche
from axelcompta.tenants.fiches_import_depot import FichesImportMemoire

T = TenantId("T")
LE = datetime(2026, 11, 18, 12, tzinfo=UTC)
PDF = b"%PDF-1.4 un document"
KBIS_LU: dict[str, object] = {
    "siren": "908771033",
    "denomination": "KERFICE SERVICE",
    "forme_juridique": "SASU",
    "siege": "",
    "code_naf": "",
    "date_immatriculation": "",
    "montants": [],
}
STATUTS_LU: dict[str, object] = {
    "forme_juridique": "SASU",
    "denomination": "",
    "siege": "",
    "date_signature": "",
    "montants": [{"nom": "capital_cts", "valeur_cts": 100000}],
    "associes": [],
}


def _fiche() -> tuple[FichesImportMemoire, str]:
    fiches = FichesImportMemoire()
    fiche = nouvelle_fiche("f", T, "Konate", "K", "908771033", "b", LE)
    fiches.enregistrer(fiche)
    for cle, emplacement, nom in (
        ("kbis", "documents:kbis", "kbis.pdf"),
        ("vrac", "documents:autre", "scan 12.pdf"),
        ("refus", "documents:lettre_comptable", "lettre.pdf"),
    ):
        contenu = PDF + cle.encode()
        fiches.deposer(document_import(cle, fiche, emplacement, nom, "", contenu, "b", LE), contenu)
    return fiches, fiche.id


def _appeler(modele: str, categorie: Categorie, contenu: bytes, _media: str) -> Appel:
    if categorie.cle == "kbis":
        return Appel(KBIS_LU, 0.001)
    if categorie.cle == "classement":
        return Appel(
            {"type_document": "statuts", "annee_exercice": "", "siren": "", "denomination": ""},
            0.0005,
        )
    if categorie.cle == "statuts":
        return Appel(STATUTS_LU, 0.002)
    # La lettre : Haiku et Sonnet échouent.
    return Appel(
        {"cabinet": "", "contact": "", "email": "", "telephone": "", "date_lettre": ""},
        0.01 if modele == SONNET else 0.0,
    )


def test_un_passage_lit_range_et_signale() -> None:
    fiches, fiche_id = _fiche()
    bilan = passer(fiches, T, _appeler, LE, plafond_usd=5.0)
    documents = {d.id: d for d in fiches.instantane(T, fiche_id).documents}

    assert documents["kbis"].statut_traitement == "traite"
    assert documents["kbis"].resume.startswith("Kbis lu : KERFICE SERVICE")
    assert documents["kbis"].donnees["ocr"]["modele"] == HAIKU  # type: ignore[index]

    vrac = documents["vrac"]
    assert (vrac.categorie, vrac.emplacement, vrac.statut_traitement) == (
        "statuts",
        "documents:statuts",
        "traite",
    )

    refus = documents["refus"]
    assert refus.statut_traitement == "a_traiter"
    assert refus.resume == "À vérifier par un humain : Cabinet : non lu."
    assert refus.donnees["ocr"]["modele"] == SONNET  # type: ignore[index]

    assert (bilan.lus, bilan.a_verifier, bilan.ranges) == (3, 1, 1)
    # Rien n'est relu au passage suivant : le document « à vérifier » attend un humain.
    assert not any(a_lire(d) for d in documents.values())
    assert passer(fiches, T, _appeler, LE, plafond_usd=5.0).phrase() == ""


def test_le_plafond_du_mois_arrete_le_passage() -> None:
    fiches, fiche_id = _fiche()
    bilan = passer(fiches, T, _appeler, LE, plafond_usd=0.0)
    assert bilan.plafond_atteint and bilan.lus == 0
    assert "plafond du mois atteint" in bilan.phrase()


def test_un_document_illisible_par_l_ocr_n_est_pas_envoye() -> None:
    assert media_type(b"%PDF-1.7") == "application/pdf"
    assert media_type(b"\x89PNG\r\n") == "image/png"
    assert media_type(b"PK\x03\x04") == ""
    fiches, fiche_id = _fiche()
    fiche = fiches.lire(T, fiche_id)
    tableur = document_import(
        "xlsx", fiche, "documents:autre", "ca.xlsx", "", b"PK\x03\x04", "b", LE
    )
    fiches.deposer(tableur, b"PK\x03\x04")
    passer(fiches, T, _appeler, LE, plafond_usd=5.0)
    reste = next(d for d in fiches.instantane(T, fiche_id).documents if d.id == "xlsx")
    assert reste == replace(tableur, statut_traitement=reste.statut_traitement)
