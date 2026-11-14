"""AXE-919 : chercher un user Rollee par son nom, dans l'annuaire du portefeuille."""

from __future__ import annotations

from datetime import UTC, datetime

from axelcompta.core.ids import TenantId
from axelcompta.ingestion.annuaire_rollee import (
    RESULTATS_MAX,
    AnnuaireRolleeMemoire,
    FicheAnnuaire,
    chercher,
    correspond,
)
from axelcompta.ingestion.rapprochement_rollee import masquer_email, normaliser_nom

T = TenantId("t")
LE = datetime(2026, 11, 14, 9, tzinfo=UTC)


def _fiche(user: str, nom: str, branchement: str = "b1", tenant: TenantId = T) -> FicheAnnuaire:
    return FicheAnnuaire(user, tenant, branchement, nom, ("uber.com-rev",), None, LE)


def test_la_recherche_ignore_accents_casse_et_ordre_des_mots() -> None:
    nom = normaliser_nom("Élodie Martin-Dupont")
    assert correspond(nom, "mart elo")
    assert correspond(nom, "ÉLODIE")
    assert correspond(nom, "dupont")
    assert not correspond(nom, "martine")
    assert not correspond(nom, "")


def test_rien_sous_deux_lettres_et_resultats_bornes_et_tries() -> None:
    fiches = [_fiche(f"u{i:03}", f"Karim Benali {i}") for i in range(30)]
    assert chercher(fiches, "k") == []
    assert len(chercher(fiches, "ka")) == RESULTATS_MAX
    autres = [_fiche("u-z", "Zoé Arnaud"), _fiche("u-a", "Anne Arnaud")]
    assert [f.nom for f in chercher(autres, "arn")] == ["Anne Arnaud", "Zoé Arnaud"]


def test_l_email_est_masque() -> None:
    assert masquer_email("elodie.martin@exemple.fr") == "e•••n@exemple.fr"
    assert masquer_email("ab@x.fr") == "a•••@x.fr"
    assert masquer_email("sans-arobase") is None
    assert masquer_email(None) is None


def test_un_passage_remplace_les_fiches_d_un_compte_et_un_passage_partiel_ajoute() -> None:
    annuaire = AnnuaireRolleeMemoire()
    annuaire.remplacer(T, "b1", [_fiche("u1", "Karim Benali"), _fiche("u2", "Anne Arnaud")])
    annuaire.remplacer(T, "b2", [_fiche("u3", "Zoé Arnaud", "b2")])
    annuaire.remplacer(T, "b1", [_fiche("u1", "Karim Benali")])
    assert {f.rollee_user_id for f in annuaire.fiches(T)} == {"u1", "u3"}
    annuaire.remplacer(T, "b1", [_fiche("u4", "Léa Morel")], partiel=True)
    assert {f.rollee_user_id for f in annuaire.fiches(T)} == {"u1", "u3", "u4"}
    assert annuaire.fiche(T, "u4") is not None
    assert annuaire.fiche(TenantId("autre"), "u4") is None
