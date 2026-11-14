"""Recherche d'un user Rollee par son nom, sur les fiches de la carte."""

from __future__ import annotations

from datetime import UTC, datetime

from axelcompta.core.ids import TenantId
from axelcompta.ingestion.annuaire_rollee import (
    RESULTATS_MAX,
    FicheAnnuaire,
    chercher,
    correspond,
    masquer_email,
)
from axelcompta.ingestion.rapprochement_rollee import normaliser_nom

T = TenantId("t")
LE = datetime(2026, 11, 14, 9, tzinfo=UTC)


def _fiche(user: str, nom: str) -> FicheAnnuaire:
    return FicheAnnuaire(user, T, "b1", nom, ("uber.com-rev",), None, LE)


def test_la_recherche_ignore_accents_casse_et_ordre_des_mots() -> None:
    nom = normaliser_nom("Élodie Martin-Dupont")
    assert correspond(nom, "mart elo")
    assert correspond(nom, "ÉLODIE")
    assert correspond(nom, "dupont")
    assert not correspond(nom, "martine")
    assert not correspond(nom, "")


def test_rien_sous_deux_lettres_et_les_resultats_sont_bornes() -> None:
    fiches = [_fiche(f"u{i:03}", f"Karim Benali {i}") for i in range(30)]
    assert chercher(fiches, "k") == []
    assert len(chercher(fiches, "ka")) == RESULTATS_MAX
    autres = [_fiche("u-z", "Zoé Arnaud"), _fiche("u-a", "Anne Arnaud")]
    assert [fiche.nom for fiche in chercher(autres, "arn")] == ["Anne Arnaud", "Zoé Arnaud"]


def test_l_email_est_masque() -> None:
    assert masquer_email("elodie.martin@exemple.fr") == "e•••n@exemple.fr"
    assert masquer_email("ab@x.fr") == "a•••@x.fr"
    assert masquer_email("sans-arobase") is None
    assert masquer_email(None) is None
