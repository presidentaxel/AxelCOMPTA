"""AXE-730 : ce qui rend un dossier ambigu, et sa confirmation."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.confirmation import (
    ConfirmationRefusee,
    confirmer,
    formes_proposees,
    identite_manquante,
    raison_ambiguite,
)
from axelcompta.tenants.models import Dossier


def _dossier(forme: str = "SASU", **champs: object) -> Dossier:
    base = Dossier(
        id=DossierId("d"),
        tenant_id=TenantId("t"),
        forme_juridique=forme,
        regime_imposition="IS" if forme != "EI" else "IR",
        regime_tva="reel_normal",
        nom="Test",
        tva_recettes_regime="assujetti_taux_reduit",
        exercice_debut=date(2025, 1, 1),
        identite=IDENTITE_KARIM,
    )
    return dataclasses.replace(base, **champs)  # type: ignore[arg-type]


def test_un_dossier_confirme_et_complet_n_est_pas_ambigu() -> None:
    assert raison_ambiguite(_dossier()) is None


def test_une_forme_proposee_par_sirene_bloque_jusqu_a_confirmation() -> None:
    dossier = _dossier("SAS", a_confirmer=("forme_juridique",))
    assert raison_ambiguite(dossier) == "Le dirigeant doit d'abord confirmer la forme juridique."
    assert formes_proposees(dossier) == ("SAS", "SASU")


def test_deux_elements_a_confirmer_dans_une_seule_phrase() -> None:
    dossier = _dossier("SARL", a_confirmer=("exercice", "forme_juridique"))
    assert raison_ambiguite(dossier) == (
        "Le dirigeant doit d'abord confirmer les dates du premier exercice et la forme juridique."
    )


def test_une_societe_sans_identite_manque_de_siege_capital_et_associes() -> None:
    dossier = _dossier(identite=None)
    assert identite_manquante(dossier) == ("siege", "capital", "associes")
    assert raison_ambiguite(dossier) == (
        "Il manque l'adresse du siège, le capital et les associés de la société."
    )


def test_capital_nul_ou_associes_absents() -> None:
    identite = dataclasses.replace(IDENTITE_KARIM, capital_social_cts=0, associes=())
    assert identite_manquante(_dossier(identite=identite)) == ("capital", "associes")


def test_un_entrepreneur_individuel_n_a_pas_de_capital_a_fournir() -> None:
    assert identite_manquante(_dossier("EI", identite=None)) == ()


def test_confirmer_choisit_la_forme_et_vide_ce_qui_restait() -> None:
    dossier = _dossier("SAS", a_confirmer=("exercice", "forme_juridique"))
    confirme = confirmer(dossier, "SASU")
    assert (confirme.forme_juridique, confirme.a_confirmer) == ("SASU", ())
    assert confirmer(dossier, None).forme_juridique == "SAS"


def test_on_ne_choisit_pas_une_forme_hors_de_la_paire_sirene() -> None:
    with pytest.raises(ConfirmationRefusee):
        confirmer(_dossier("SAS", a_confirmer=("forme_juridique",)), "EURL")
    with pytest.raises(ConfirmationRefusee):
        confirmer(_dossier("SASU"), "SAS")  # forme déjà certaine
