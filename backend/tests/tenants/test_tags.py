from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from axelcompta.core.ids import DossierId, TenantId, UserId
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.tags import (
    EXCLUSIONS_PAR_DEFAUT,
    SANS_TAGS,
    TAG_CHAUFFEUR,
    TAG_SOCIETE_DU_GESTIONNAIRE,
    TRAITEMENTS,
    EtatTags,
    Tag,
    TagInvalide,
    a_taguer_chauffeur,
    est_exclu,
    etat_du_portefeuille,
    exclus,
    exclusions_completes,
    nom_de_tag,
    retenus,
    tag_depuis_naf,
)
from axelcompta.tenants.tags_memoire import TagsMemoire

SERENITY = TenantId("TENANT_DEMO")
AUTRE = TenantId("autre")
GROUPE = DossierId("DIGI_4952")
MK = DossierId("DIGI_22755")
LOUIS = UserId("louis")
LE = datetime(2026, 11, 5, tzinfo=UTC)


def test_nom_de_tag() -> None:
    assert nom_de_tag("Flotte Nord") == "flotte_nord"
    for invalide in ("", "a", "société", "x" * 41, "-tiret", "point.virgule"):
        with pytest.raises(TagInvalide):
            nom_de_tag(invalide)


def test_par_defaut_les_societes_du_gestionnaire_sont_exclues_de_tout() -> None:
    assert set(EXCLUSIONS_PAR_DEFAUT) == set(TRAITEMENTS)
    for traitement in TRAITEMENTS:
        assert est_exclu({TAG_SOCIETE_DU_GESTIONNAIRE}, EXCLUSIONS_PAR_DEFAUT, traitement)
        assert not est_exclu({TAG_CHAUFFEUR}, EXCLUSIONS_PAR_DEFAUT, traitement)
        assert not est_exclu(set(), EXCLUSIONS_PAR_DEFAUT, traitement)


def test_un_traitement_inconnu_est_refuse() -> None:
    with pytest.raises(TagInvalide):
        est_exclu({"x"}, EXCLUSIONS_PAR_DEFAUT, "inventé")


def test_un_reglage_enregistre_l_emporte_sur_le_defaut() -> None:
    completes = exclusions_completes({"synchro": frozenset()})
    assert completes["synchro"] == frozenset()
    assert completes["expert"] == EXCLUSIONS_PAR_DEFAUT["expert"]


def test_tag_depuis_naf() -> None:
    assert tag_depuis_naf("49.32Z") == TAG_CHAUFFEUR
    assert tag_depuis_naf("70.22Z") is None
    assert tag_depuis_naf(None) is None


def test_poser_retirer_et_etat() -> None:
    depot = TagsMemoire()
    depot.poser(SERENITY, GROUPE, TAG_SOCIETE_DU_GESTIONNAIRE, LOUIS, LE)
    depot.poser(SERENITY, GROUPE, TAG_SOCIETE_DU_GESTIONNAIRE, LOUIS, LE)  # sans effet
    depot.poser(SERENITY, MK, TAG_CHAUFFEUR, LOUIS, LE)
    etat = etat_du_portefeuille(depot, SERENITY)
    assert etat.exclu(GROUPE, "expert")
    assert not etat.exclu(MK, "expert")

    depot.retirer(SERENITY, GROUPE, TAG_SOCIETE_DU_GESTIONNAIRE, LOUIS, LE)

    assert not etat_du_portefeuille(depot, SERENITY).exclu(GROUPE, "expert")
    assert depot.tags_des_dossiers(SERENITY) == {MK: frozenset({TAG_CHAUFFEUR})}
    assert depot.tags_des_dossiers(AUTRE) == {}


def test_un_tag_inconnu_ne_se_pose_pas_mais_un_tag_cree_oui() -> None:
    depot = TagsMemoire()
    with pytest.raises(TagInvalide):
        depot.poser(SERENITY, MK, "flotte_nord", LOUIS, LE)
    depot.creer_tag(Tag(SERENITY, "flotte_nord", "Flotte du nord"))
    depot.poser(SERENITY, MK, "flotte_nord", LOUIS, LE)
    assert "flotte_nord" in {t.nom for t in depot.lister_tags(SERENITY)}
    assert "flotte_nord" not in {t.nom for t in depot.lister_tags(AUTRE)}


def test_regler_une_exclusion() -> None:
    depot = TagsMemoire()
    depot.poser(SERENITY, GROUPE, TAG_SOCIETE_DU_GESTIONNAIRE, LOUIS, LE)
    depot.regler_exclusion(SERENITY, "synchro", frozenset(), LOUIS, LE)
    etat = etat_du_portefeuille(depot, SERENITY)
    assert not etat.exclu(GROUPE, "synchro")
    assert etat.exclu(GROUPE, "expert")
    with pytest.raises(TagInvalide):
        depot.regler_exclusion(SERENITY, "inventé", frozenset(), LOUIS, LE)


def test_un_etat_vide_n_exclut_rien() -> None:
    assert not EtatTags({}, EXCLUSIONS_PAR_DEFAUT).exclu(MK, "synchro")


def test_seuls_les_dossiers_vtc_recoivent_le_tag_chauffeur() -> None:
    base = Dossier(
        id=MK,
        tenant_id=SERENITY,
        forme_juridique="SAS",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="MK",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 1),
        code_naf="49.32Z",
    )
    groupe = replace(base, id=GROUPE, code_naf="70.22Z")
    sans_naf = replace(base, id=DossierId("DIGI_2"), code_naf=None)
    assert a_taguer_chauffeur([base, groupe, sans_naf]) == (MK,)


def test_retenus_et_exclus() -> None:
    base = Dossier(
        id=MK,
        tenant_id=SERENITY,
        forme_juridique="SAS",
        regime_imposition="IS",
        regime_tva="franchise",
        nom="MK",
        tva_recettes_regime="franchise",
        exercice_debut=date(2026, 1, 1),
    )
    groupe = replace(base, id=GROUPE)
    etat = EtatTags({GROUPE: frozenset({TAG_SOCIETE_DU_GESTIONNAIRE})}, EXCLUSIONS_PAR_DEFAUT)
    assert retenus([base, groupe], etat, "synchro") == (base,)
    assert exclus([base, groupe], etat, "synchro") == frozenset({GROUPE})
    assert retenus([base, groupe], SANS_TAGS, "synchro") == (base, groupe)
