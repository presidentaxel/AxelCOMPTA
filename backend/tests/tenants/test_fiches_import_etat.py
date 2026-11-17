"""AXE-941, AXE-947 : exercices, emplacements de documents, ce qui manque et
statut d'une fiche d'import."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.fiches_import import (
    DocumentImport,
    FicheImport,
    cle_archive,
    document_import,
    modifier,
    nouvelle_fiche,
)
from axelcompta.tenants.fiches_import_depot import ContenusMemoire, FichesImportMemoire, deplacer
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
    """AXE-947 : jamais choisi à la main, sauf Ignoré qui reste jusqu'à reprise."""
    vide = nouvelle_fiche("f1", T, "Dupont", "Karim", "", "b", LE)
    assert statut_calcule(vide, [], AUJOURD_HUI) == "a_importer"
    assert statut_calcule(_fiche(email="k@x.fr"), [], AUJOURD_HUI) == "en_traitement"
    ignoree = replace(vide, statut="ignore")
    assert statut_calcule(ignoree, [], AUJOURD_HUI) == "ignore"


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
    assert len(manque_pour_creer(_fiche())) == 4
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


def test_une_fiche_sans_regime_devient_un_dossier_a_confirmer() -> None:
    fiche = _fiche(
        siren="883828527",
        denomination="DF TRANSPORTS",
        forme_juridique="SASU",
        exercice_debut="2026-01-01",
    )
    reliee, dossier, erreurs = relier_au_portefeuille(fiche, ())
    assert erreurs == ()
    assert dossier is not None
    assert reliee.dossier_id == dossier.id == DossierId("SIREN_883828527")
    assert (dossier.regime_imposition, dossier.regime_tva) == ("IS", "reel_normal")
    assert dossier.a_confirmer == ("imposition",)


def test_une_fiche_ignoree_ne_cree_pas_de_dossier() -> None:
    fiche = replace(
        _fiche(
            siren="883828527",
            denomination="DF TRANSPORTS",
            forme_juridique="SASU",
            exercice_debut="2026-01-01",
        ),
        statut="ignore",
    )
    assert relier_au_portefeuille(fiche, ()) == (fiche, None, ())


# --- AXE-970 : tout exercice, depuis 2000 ---------------------------------


def test_un_exercice_ajoute_ou_garni_apparait_meme_avant_2024() -> None:
    champs = {
        "date_creation": "2022-01-03",
        "cloture": "30/09",
        "premiere_cloture": "2022-09-30",
        "exercices_ajoutes": "2019",
    }
    fiche = nouvelle_fiche("f", TenantId("T"), "D", "K", "", "b", LE)
    document = document_import("d", fiche, "reprise:piece:2022", "ENC-1.pdf", "", b"%", "b", LE)
    liste = exercices(champs, AUJOURD_HUI, [document])
    assert [(e.annee, e.role) for e in liste] == [
        (2019, "anterieur"),
        (2022, "anterieur"),
        (2024, "anterieur"),
        (2025, "source"),
        (2026, "a_declarer"),
        (2027, "en_cours"),
    ]
    assert (liste[0].debut, liste[0].fin) == (date(2018, 10, 1), date(2019, 9, 30))


def test_une_piece_classee_a_sa_carte_dans_son_exercice() -> None:
    fiche = nouvelle_fiche("f", TenantId("T"), "D", "K", "", "b", LE)
    document = document_import("d", fiche, "reprise:piece:2022", "ENC-1.pdf", "", b"%", "b", LE)
    champs = {"date_creation": "2022-01-03", "cloture": "30/09"}
    cartes = {e.cle: e for e in emplacements(champs, [document], AUJOURD_HUI)}
    assert "reprise:liasse:2022" in cartes  # l'exercice garni a ses cartes de base
    piece = cartes["reprise:piece:2022"]
    assert (piece.libelle, piece.explication, len(piece.documents)) == (
        "Pièces justificatives 2022",
        "Factures, reçus, encaissements.",
        1,
    )


def test_le_depot_en_memoire_range_deplace_et_retire_avec_l_archive() -> None:
    fiche = nouvelle_fiche("f", TenantId("T"), "D", "K", "", "b", LE)
    depot = FichesImportMemoire()
    depot.enregistrer(fiche)
    archive = document_import("z", fiche, "reprise:archive:2022", "a.zip", "", b"PK", "b", LE)
    membre = replace(
        document_import("m", fiche, "reprise:autre:2022", "x.pdf", "", b"%", "b", LE),
        origine_id="z",
    )
    depot.deposer_lot([(archive, b"PK"), (membre, b"%")])
    range_ = depot.ranger(replace(membre, categorie="liasse", emplacement="reprise:liasse:2022"))
    assert [d.categorie for d in range_.documents] == ["archive", "liasse"]
    assert depot.retirer(TenantId("T"), "f", "z").documents == []


def test_un_document_reclasse_change_de_place_dans_le_bucket() -> None:
    fiche = nouvelle_fiche("f", TenantId("T"), "D", "K", "", "b", LE)
    bucket = ContenusMemoire()
    document = document_import("d" * 12, fiche, "reprise:autre:2022", "x.pdf", "", b"%", "b", LE)
    document = replace(document, cle_stockage=cle_archive(document))
    bucket.ecrire(document.cle_stockage, b"%")
    deplace = deplacer(bucket, replace(document, categorie="liasse", exercice=2021))
    assert deplace.cle_stockage == "T/imports/f/2021/liasse/dddddddddddd-x.pdf"
    assert bucket.objets == {deplace.cle_stockage: b"%"}


def test_les_releves_restent_obligatoires_tant_que_l_exercice_a_declarer_n_est_pas_couvert() -> (
    None
):
    """AXE-971, KERFICE : Digifactory couvre l'exercice en cours (ouvert le
    01/10/2026) mais pas celui clos le 30/09/2026, à déclarer par nous."""
    champs = {
        "date_creation": "2022-01-03",
        "cloture": "30/09",
        "contact_digifactory": "24951",
        "debut_historique": "2026-08-20",
        "exercice_debut": "2026-10-01",
    }
    aujourd_hui = date(2026, 11, 17)
    releves = next(
        e for e in emplacements(champs, [], aujourd_hui) if e.cle == "banque:releve_bancaire"
    )
    assert releves.attendu
    assert releves.explication.startswith("Du 01/10/2025 au 19/08/2026")

    couvert = {**champs, "debut_historique": "2025-09-01"}
    facultatif = next(
        e for e in emplacements(couvert, [], aujourd_hui) if e.cle == "banque:releve_bancaire"
    )
    assert not facultatif.attendu
    assert facultatif.explication.startswith("Digifactory remonte tout depuis le 01/09/2025")

    sans_historique = {k: v for k, v in champs.items() if k != "debut_historique"}
    inconnu = next(
        e
        for e in emplacements(sans_historique, [], aujourd_hui)
        if e.cle == "banque:releve_bancaire"
    )
    assert inconnu.attendu and "du 01/10/2025 à aujourd'hui" in inconnu.explication
