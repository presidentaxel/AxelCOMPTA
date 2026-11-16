"""AXE-941 : exercices à reprendre et ce qui manque à une fiche d'import."""

from __future__ import annotations

from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.fiches_import import DocumentImport, FicheImport, modifier, nouvelle_fiche
from axelcompta.tenants.fiches_import_etat import (
    dossier_prevu,
    etat_sections,
    exercices,
    ligne_dossier,
    manque_pour_creer,
)
from axelcompta.tenants.import_dossiers import rapport

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 16)
T = TenantId("TENANT_DEMO")


def _document(categorie: str, exercice: int | None) -> DocumentImport:
    return DocumentImport(
        f"{categorie}-{exercice}",
        "f1",
        T,
        categorie,
        exercice,
        "x",
        "application/pdf",
        1,
        "e",
        "b",
        LE,
    )


def _fiche(**champs: str) -> FicheImport:
    return modifier(nouvelle_fiche("f1", T, "Dupont", "Karim", "", "b", LE), champs, "b", LE)


def test_une_societe_de_2023_reprend_2024_et_2025_et_le_dernier_clos_est_indispensable() -> None:
    champs = {"date_creation": "2023-03-15", "cloture": "31/12"}
    liste = exercices(champs, [_document("fec", 2025)], AUJOURD_HUI)

    assert [(e.annee, e.etat) for e in liste] == [
        (2024, "clos"),
        (2025, "clos"),
        (2026, "en_cours"),
    ]
    assert (liste[0].debut, liste[0].fin) == (date(2024, 1, 1), date(2024, 12, 31))
    en_2025 = {p.categorie: p for p in liste[1].pieces}
    assert en_2025["liasse"].attendue and not en_2025["liasse"].recue
    assert en_2025["fec"].recue
    assert not en_2025["balance"].attendue  # le FEC suffit
    assert not any(p.attendue for p in liste[0].pieces)  # 2024 : si disponible
    assert liste[2].pieces == ()


def test_un_premier_exercice_long_suit_la_date_de_premiere_cloture() -> None:
    champs = {"date_creation": "2025-06-10", "cloture": "31/12", "premiere_cloture": "2026-12-31"}
    assert [(e.debut, e.fin, e.etat) for e in exercices(champs, [], AUJOURD_HUI)] == [
        (date(2025, 6, 10), date(2026, 12, 31), "en_cours")
    ]


def test_une_cloture_au_29_fevrier_tombe_au_28_les_autres_annees() -> None:
    champs = {"date_creation": "2023-03-01", "cloture": "29/02"}
    fins = [e.fin for e in exercices(champs, [], AUJOURD_HUI)]
    assert fins == [date(2024, 2, 29), date(2025, 2, 28), date(2026, 2, 28), date(2027, 2, 28)]


def test_sans_date_de_creation_ni_cloture_rien_n_est_calcule() -> None:
    assert exercices({"cloture": "31/12"}, [], AUJOURD_HUI) == []
    reprise = next(e for e in etat_sections(_fiche(), [], AUJOURD_HUI) if e.cle == "reprise")
    assert reprise.manquants == ("Date de création et date de clôture (catégorie Entreprise)",)


def test_chaque_categorie_dit_ce_qui_lui_manque() -> None:
    fiche = _fiche(
        date_creation="2023-03-15",
        cloture="31/12",
        regime_imposition="option_IR",
        email="k@x.fr",
    )
    documents = [_document("liasse", 2025), _document("balance", 2025), _document("kbis", None)]
    etats = {e.cle: e for e in etat_sections(fiche, documents, AUJOURD_HUI)}

    assert etats["dirigeant"].complet
    assert "Première année de l'option IR" in etats["fiscalite"].manquants
    assert etats["reprise"].manquants == ("FEC 2025", "Grand livre 2025")
    assert etats["documents"].manquants == ("Statuts", "RIB")
    assert "SIREN" in etats["entreprise"].manquants


def test_la_fiche_complete_devient_une_ligne_d_import_valide() -> None:
    fiche = _fiche(
        siren="552100554",
        denomination="MK DRIVING",
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        exercice_debut="2026-01-01",
        contact_digifactory="contact 22755",
    )
    assert manque_pour_creer(fiche) == []
    assert manque_pour_creer(_fiche()) == [
        "SIREN",
        "Dénomination",
        "Forme juridique",
        "Imposition des bénéfices",
        "Régime de TVA",
        "Début de l'exercice en cours",
    ]
    (ligne,) = rapport(T, [ligne_dossier(fiche)], []).lignes
    assert ligne.dossier is not None and ligne.erreurs == ()
    assert ligne.dossier.id == DossierId("DIGI_22755") == dossier_prevu(fiche)
    assert ligne.dossier.tva_recettes_regime == "assujetti_taux_reduit"
