"""AXE-995 : un document mal rangé, vu par l'OCR, change seul de catégorie
quand il tient dans la nouvelle, sinon la catégorie est proposée."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from axelcompta.core.ids import TenantId
from axelcompta.ocr.categories import Categorie
from axelcompta.ocr.lecture import Appel
from axelcompta.ocr.passage import a_lire, depense_du_mois, passer
from axelcompta.ocr.reclassement import PROPOSITION, RANGE_PAR, RECLASSEMENT, proposition
from axelcompta.tenants.fiches_import import (
    CATEGORIES_DOCUMENTS,
    DocumentImport,
    document_import,
    nouvelle_fiche,
)
from axelcompta.tenants.fiches_import_depot import FichesImportMemoire

T = TenantId("T")
LE = datetime(2026, 11, 19, 3, tzinfo=UTC)
PDF = b"%PDF-1.4 teletransmission"

# « Télétransmission SEVEN CAR PRESTIGE.pdf », rangé en liasse : l'accusé
# EDI n'a pas de résultat, la lecture de liasse échoue, et dit ce qu'il est.
LIASSE_LUE: dict[str, object] = {
    "siren": "",
    "denomination": "SEVEN CAR PRESTIGE",
    "formulaire": "2065",
    "exercice_debut": "",
    "exercice_fin": "2023-12-31",
    "montants": [],
    "nature_constatee": "accuse_reception",
}
ACCUSE_LU: dict[str, object] = {
    "declaration": "Liasse 2065",
    "date_depot": "2024-04-30",
    "numero": "EDI-123",
    "periode": "2023",
    "siren": "",
    "nature_constatee": "accuse_reception",
}


class Appels:
    def __init__(self, accuse: dict[str, object] | None = ACCUSE_LU) -> None:
        self.categories: list[str] = []
        self.accuse = accuse

    def __call__(self, _modele: str, categorie: Categorie, _c: bytes, _m: str) -> Appel:
        self.categories.append(categorie.cle)
        if categorie.cle == "liasse":
            return Appel(LIASSE_LUE, 0.01)
        return Appel(self.accuse, 0.002)


def _fiche(donnees: dict[str, object] | None = None) -> tuple[FichesImportMemoire, str]:
    fiches = FichesImportMemoire()
    fiche = nouvelle_fiche("f", T, "Seven", "S", "833160435", "b", LE)
    fiches.enregistrer(fiche)
    doc = document_import(
        "edi", fiche, "reprise:liasse:2023", "Télétransmission.pdf", "", PDF, "b", LE
    )
    fiches.deposer(replace(doc, donnees=donnees), PDF)
    return fiches, fiche.id


def _document(fiches: FichesImportMemoire, fiche_id: str) -> DocumentImport:
    return next(d for d in fiches.instantane(T, fiche_id).documents if d.id == "edi")


def test_un_accuse_range_en_liasse_est_reclasse_quand_il_tient_comme_accuse() -> None:
    fiches, fiche_id = _fiche()
    appels = Appels()
    bilan = passer(fiches, T, appels, LE, plafond_usd=5.0)
    doc = _document(fiches, fiche_id)

    assert (doc.categorie, doc.emplacement, doc.statut_traitement) == (
        "accuse_reception",
        "reprise:accuse_reception:2023",
        "traite",
    )
    assert doc.resume.startswith("Reclassé par l'OCR : était ")
    assert "Accusé de dépôt : Liasse 2065, le 2024-04-30." in doc.resume
    trace = (doc.donnees or {})[RECLASSEMENT]
    assert isinstance(trace, dict)
    assert (trace["de"], trace["vers"]) == ("liasse", "accuse_reception")
    assert PROPOSITION not in (doc.donnees or {})
    # Haiku et Sonnet en liasse, puis Haiku suffit en accusé.
    assert appels.categories == ["liasse", "liasse", "accuse_reception"]
    assert (bilan.lus, bilan.reclasses, bilan.a_verifier) == (1, 1, 0)
    # Chaque lecture compte une fois dans la dépense du mois.
    assert round(depense_du_mois([doc], LE), 6) == 0.022
    assert not a_lire(doc)


def test_sans_lecture_valide_dans_la_categorie_constatee_le_document_ne_bouge_pas() -> None:
    fiches, fiche_id = _fiche()
    illisible = {**ACCUSE_LU, "date_depot": ""}
    bilan = passer(fiches, T, Appels(accuse=illisible), LE, plafond_usd=5.0)
    doc = _document(fiches, fiche_id)

    assert (doc.categorie, doc.statut_traitement) == ("liasse", "a_traiter")
    libelle = CATEGORIES_DOCUMENTS["accuse_reception"]
    assert doc.resume.endswith(f"Ce document semble être : {libelle}.")
    assert proposition(doc.donnees) == "accuse_reception"
    assert (bilan.reclasses, bilan.a_verifier) == (0, 1)
    assert round(depense_du_mois([doc], LE), 6) == 0.024


def test_un_document_range_a_la_main_n_est_jamais_deplace_d_office() -> None:
    fiches, fiche_id = _fiche({RANGE_PAR: "humain"})
    appels = Appels()
    passer(fiches, T, appels, LE, plafond_usd=5.0)
    doc = _document(fiches, fiche_id)

    assert doc.categorie == "liasse"
    assert proposition(doc.donnees) == "accuse_reception"
    assert "accuse_reception" not in appels.categories  # pas de relecture


def test_la_bonne_categorie_ne_propose_rien() -> None:
    fiches2 = FichesImportMemoire()
    fiche = nouvelle_fiche("f", T, "Seven", "S", "833160435", "b", LE)
    fiches2.enregistrer(fiche)
    doc = document_import(
        "edi", fiche, "reprise:accuse_reception:2023", "Accusé.pdf", "", PDF, "b", LE
    )
    fiches2.deposer(doc, PDF)
    appels = Appels()
    passer(fiches2, T, appels, LE, plafond_usd=5.0)
    lu = _document(fiches2, fiche.id)
    assert lu.statut_traitement == "traite"
    assert proposition(lu.donnees) is None
    assert appels.categories == ["accuse_reception"]


def test_la_nature_constatee_est_demandee_a_chaque_categorie_sauf_au_classement() -> None:
    from axelcompta.ocr.documents import CLASSEMENT
    from axelcompta.ocr.reprise import LIASSE

    assert "nature_constatee" in LIASSE.schema()["required"]
    assert "« liasse »" in LIASSE.consigne_complete()
    assert "nature_constatee" not in CLASSEMENT.schema()["properties"]
