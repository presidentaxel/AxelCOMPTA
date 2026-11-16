"""AXE-941, AXE-947 : exercices, emplacements de documents, ce qui manque et
statut d'une fiche d'import."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.fiches_import import DocumentImport, FicheImport, modifier, nouvelle_fiche
from axelcompta.tenants.fiches_import_etat import (
    ContactDigifactory,
    contacts_correspondants,
    dossier_prevu,
    emplacements,
    etat_sections,
    exercices,
    ligne_dossier,
    manque_pour_creer,
    relier_au_portefeuille,
    statut_calcule,
)
from axelcompta.tenants.import_dossiers import rapport
from axelcompta.tenants.models import Dossier

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
AUJOURD_HUI = date(2026, 11, 16)
T = TenantId("TENANT_DEMO")
CREE_EN_2023 = {"date_creation": "2023-03-15", "cloture": "31/12"}


def _document(emplacement: str, statut: str = "a_traiter") -> DocumentImport:
    _section, categorie, *annee = emplacement.split(":")
    return DocumentImport(
        emplacement,
        "f1",
        T,
        categorie,
        int(annee[0]) if annee else None,
        "x",
        "application/pdf",
        1,
        "e",
        "b",
        LE,
        emplacement=emplacement,
        statut_traitement=statut,  # type: ignore[arg-type]
    )


def _fiche(**champs: str) -> FicheImport:
    return modifier(nouvelle_fiche("f1", T, "Dupont", "Karim", "", "b", LE), champs, "b", LE)


def test_une_societe_de_2023_reprend_2024_et_2025_et_le_dernier_clos_est_indispensable() -> None:
    assert [(e.annee, e.etat) for e in exercices(CREE_EN_2023, AUJOURD_HUI)] == [
        (2024, "clos"),
        (2025, "clos"),
        (2026, "en_cours"),
    ]
    places = {e.cle: e for e in emplacements(CREE_EN_2023, [], AUJOURD_HUI)}
    assert places["reprise:liasse:2025"].attendu and places["reprise:fec:2025"].attendu
    assert not places["reprise:liasse:2024"].attendu  # si disponible
    assert not places["reprise:balance:2025"].attendu
    assert "report à nouveau" in places["reprise:liasse:2025"].explication


def test_un_premier_exercice_long_et_une_cloture_au_29_fevrier() -> None:
    long_ = {"date_creation": "2025-06-10", "cloture": "31/12", "premiere_cloture": "2026-12-31"}
    assert [(e.debut, e.fin) for e in exercices(long_, AUJOURD_HUI)] == [
        (date(2025, 6, 10), date(2026, 12, 31))
    ]
    bissextile = {"date_creation": "2023-03-01", "cloture": "29/02"}
    assert [e.fin for e in exercices(bissextile, AUJOURD_HUI)] == [
        date(2024, 2, 29),
        date(2025, 2, 28),
        date(2026, 2, 28),
        date(2027, 2, 28),
    ]


def test_les_releves_d_avant_digifactory_ont_leur_emplacement_et_leur_explication() -> None:
    sans_digi = emplacements({}, [], AUJOURD_HUI)
    releves = next(e for e in sans_digi if e.cle == "banque:releve_bancaire")
    assert releves.attendu and "pas encore connectée" in releves.explication

    champs = {
        "contact_digifactory": "22755",
        "exercice_debut": "2026-01-01",
        "debut_historique": "2026-06-01",
    }
    avant = next(
        e for e in emplacements(champs, [], AUJOURD_HUI) if e.cle == "banque:releve_bancaire"
    )
    assert avant.attendu
    assert avant.explication.startswith("Du 01/01/2026 au 31/05/2026")


def test_un_document_va_dans_son_emplacement_et_un_ancien_dans_celui_de_sa_categorie() -> None:
    liasse = _document("reprise:liasse:2025")
    ancien = replace(_document("documents:kbis"), emplacement="")
    places = {e.cle: e for e in emplacements(CREE_EN_2023, [liasse, ancien], AUJOURD_HUI)}
    assert places["reprise:liasse:2025"].documents == (liasse,)
    assert places["documents:kbis"].documents == (ancien,)


def test_chaque_categorie_dit_ce_qui_lui_manque() -> None:
    fiche = _fiche(**CREE_EN_2023, regime_imposition="option_IR", email="k@x.fr")
    documents = [_document("reprise:liasse:2025"), _document("documents:kbis")]
    etats = {e.cle: e for e in etat_sections(fiche, documents, AUJOURD_HUI)}

    assert etats["dirigeant"].complet
    assert "Première année de l'option IR" in etats["fiscalite"].manquants
    assert etats["reprise"].manquants == ("FEC 2025",)
    assert etats["documents"].manquants == ("Statuts",)
    assert "RIB" in etats["banque"].manquants
    assert "SIREN ou SIRET" in etats["entreprise"].manquants


def test_des_parts_qui_ne_font_pas_100_pourcent_sont_signalees() -> None:
    fiche = _fiche(
        email="k@x.fr",
        associes='[{"nom": "Dupont", "fonction": "president", "pourcentage": "60"}]',
    )
    dirigeant = next(e for e in etat_sections(fiche, [], AUJOURD_HUI) if e.cle == "dirigeant")
    assert dirigeant.manquants == ("Parts des associés : 60 % sur 100 %",)


def test_le_statut_se_calcule_tout_seul() -> None:
    """AXE-947 : jamais choisi à la main."""
    vide = nouvelle_fiche("f1", T, "Dupont", "Karim", "", "b", LE)
    assert statut_calcule(vide, [], AUJOURD_HUI) == "a_importer"
    assert statut_calcule(_fiche(email="k@x.fr"), [], AUJOURD_HUI) == "en_traitement"


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
    assert len(manque_pour_creer(_fiche())) == 6
    (ligne,) = rapport(T, [ligne_dossier(fiche)], []).lignes
    assert ligne.dossier is not None and ligne.erreurs == ()
    assert ligne.dossier.id == DossierId("DIGI_22755") == dossier_prevu(fiche)


def test_le_contact_digifactory_se_trouve_par_le_siren_ou_le_nom() -> None:
    fiche = _fiche(siren="552100554", denomination="MK Driving")
    contacts = [
        ContactDigifactory("1", "SARL AUTRE", "552100554"),
        ContactDigifactory("2", "MK DRIVING VTC", None),
        ContactDigifactory("3", "Dupont Karim", None),
        ContactDigifactory("4", "Karima Martin", None),
    ]
    trouves = [(c.contact.contact_nr, c.raison) for c in contacts_correspondants(fiche, contacts)]
    assert trouves == [("1", "même SIREN"), ("3", "même nom"), ("2", "même nom")]


CLOTURE_30_09 = {"date_creation": "2022-10-01", "cloture": "30/09"}


def test_un_exercice_dont_la_liasse_n_est_pas_due_est_a_declarer_par_nous() -> None:
    """AXE-950, cas de Louis le 16/11 : clôture au 30/09/2026, liasse due le
    15/01/2027. On la déclare ; on récupère celle du 30/09/2025."""
    roles = {e.annee: (e.role, e.echeance) for e in exercices(CLOTURE_30_09, AUJOURD_HUI)}
    assert roles[2026] == ("a_declarer", date(2027, 1, 15))
    assert roles[2025] == ("source", date(2026, 1, 15))
    assert roles[2024][0] == "anterieur"
    assert roles[2027][0] == "en_cours"

    places = {e.cle: e for e in emplacements(CLOTURE_30_09, [], AUJOURD_HUI)}
    assert "reprise:liasse:2026" not in places
    assert not places["reprise:fec:2026"].attendu  # écritures déjà saisies, si elles existent
    assert places["reprise:liasse:2025"].attendu and places["reprise:fec:2025"].attendu
    assert "pour déclarer l'exercice 2026" in places["reprise:liasse:2025"].explication


def test_une_liasse_jamais_deposee_fait_remonter_a_l_exercice_d_avant() -> None:
    en_retard = {**CLOTURE_30_09, "en_retard": "2025"}
    roles = {e.annee: (e.role, e.en_retard) for e in exercices(en_retard, AUJOURD_HUI)}
    assert roles[2025] == ("a_declarer", True)
    assert roles[2024] == ("source", False)
    fiche = _fiche(**en_retard)
    reprise = next(e for e in etat_sections(fiche, [], AUJOURD_HUI) if e.cle == "reprise")
    assert reprise.manquants == ("Liasse fiscale 2024", "FEC 2024")


def test_une_societe_dont_aucun_exercice_n_est_encore_du_n_a_rien_a_fournir() -> None:
    jeune = {
        "date_creation": "2025-10-01",
        "cloture": "30/09",
    }  # premier exercice clos le 30/09/2026
    assert [e.role for e in exercices(jeune, AUJOURD_HUI)] == ["a_declarer", "en_cours"]
    reprise = next(e for e in etat_sections(_fiche(**jeune), [], AUJOURD_HUI) if e.cle == "reprise")
    assert reprise.complet


def test_le_meme_siren_relie_la_fiche_sans_creer_un_second_dossier() -> None:
    deja = Dossier(
        id=DossierId("DIGI_10"),
        tenant_id=T,
        forme_juridique="SASU",
        regime_imposition="IS",
        regime_tva="reel_normal",
        nom="MK DRIVING",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2026, 1, 1),
        siren="552100554",
    )
    fiche = _fiche(siren="552100554", denomination="MK DRIVING")
    reliee, a_creer, erreurs = relier_au_portefeuille(fiche, (deja,))
    assert (reliee.dossier_id, a_creer, erreurs) == (DossierId("DIGI_10"), None, ())
