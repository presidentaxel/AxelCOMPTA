"""AXE-952 : une fiche d'import pour chaque entreprise déjà au portefeuille."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.fiches_import import annuler, modifier, nouvelle_fiche
from axelcompta.tenants.fiches_import_dossiers import (
    CompteRolleeDuDossier,
    DonneesDossier,
    champs_du_dossier,
    completer_portefeuille,
    fiche_du_dossier,
)
from axelcompta.tenants.models import Dossier

LE = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
T = TenantId("TENANT_DEMO")
DOSSIER = Dossier(
    id=DossierId("DIGI_22755"),
    tenant_id=T,
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="MK DRIVING",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
    contact_nr="22755",
    code_naf="49.32Z",
    siren="552100554",
    plateformes=("uber",),
)
DONNEES = DonneesDossier(
    DOSSIER,
    comptes_rollee=(CompteRolleeDuDossier("u1", "Karim Dupont", ("bolt", "uber")),),
    comptes_bancaires=("Compte pro (retenu)",),
    debut_historique=date(2026, 6, 1),
)


def test_ce_qu_on_sait_d_un_dossier_remplit_sa_fiche() -> None:
    champs = champs_du_dossier(DONNEES)
    assert champs["denomination"] == "MK DRIVING"
    assert (champs["siren"], champs["forme_juridique"], champs["regime_tva"]) == (
        "552100554",
        "SASU",
        "reel_normal",
    )
    assert (champs["contact_digifactory"], champs["debut_historique"]) == ("22755", "2026-06-01")
    assert champs["plateformes"] == "bolt,uber"
    assert json.loads(champs["comptes_rollee"])[0]["rollee_user_id"] == "u1"
    assert champs["exercice_fin"] == "2026-12-31"
    assert "deficits" not in champs  # 0 : rien à reprendre


def test_un_dossier_sans_fiche_en_recoit_une_reliee_a_lui() -> None:
    fiche = fiche_du_dossier(DONNEES, [], LE)
    assert fiche is not None
    assert (fiche.id, fiche.dossier_id, fiche.cree_par) == (
        "dossier-DIGI_22755",
        "DIGI_22755",
        "synchro",
    )
    assert fiche.champs["numero_tva"] == "FR96552100554"  # déduit du SIREN
    assert fiche_du_dossier(DONNEES, [fiche], LE) is None  # rien de plus à remplir


def test_une_fiche_ouverte_au_meme_siren_est_reprise_sans_ecraser_la_saisie() -> None:
    ouverte = modifier(
        nouvelle_fiche("f1", T, "Dupont", "Karim", "552100554", "louis", LE),
        {"denomination": "MK DRIVING VTC"},
        "louis",
        LE,
    )
    reprise = fiche_du_dossier(DONNEES, [ouverte], LE)
    assert reprise is not None
    assert (reprise.id, reprise.dossier_id) == ("f1", "DIGI_22755")
    assert reprise.champs["denomination"] == "MK DRIVING VTC"  # saisie gardée
    assert reprise.champs["contact_digifactory"] == "22755"  # vide, complété


def test_une_fiche_annulee_du_dossier_ne_revient_pas_mais_une_autre_n_empeche_rien() -> None:
    sienne = fiche_du_dossier(DONNEES, [], LE)
    assert sienne is not None
    assert fiche_du_dossier(DONNEES, [annuler(sienne, "louis", LE)], LE) is None
    essai = annuler(nouvelle_fiche("essai", T, "Test", "", "552100554", "louis", LE), "louis", LE)
    creee = fiche_du_dossier(DONNEES, [essai], LE)
    assert creee is not None and creee.id == "dossier-DIGI_22755"


def test_le_portefeuille_compte_les_fiches_creees_et_completees_sans_les_dossiers_retires() -> None:
    retire = DonneesDossier(replace(DOSSIER, id=DossierId("DIGI_1"), retire_le=date(2026, 10, 1)))
    autre = DonneesDossier(replace(DOSSIER, id=DossierId("DIGI_2"), siren="443061841"))
    vieille = nouvelle_fiche("f1", T, "Dupont", "", "552100554", "louis", LE)
    a_ecrire, creees, completees = completer_portefeuille([DONNEES, retire, autre], [vieille], LE)
    assert [f.id for f in a_ecrire] == ["f1", "dossier-DIGI_2"]
    assert (creees, completees) == (1, 1)
