from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.models import Dossier
from axelcompta.tenants.sirene import (
    FicheSirene,
    configurer_depuis_sirene,
    fiche_depuis_reponse,
    forme_depuis_nature,
)
from axelcompta.tenants.statuts import configuration_de

AUJOURD_HUI = date(2026, 11, 5)
DOSSIER = Dossier(
    id=DossierId("DIGI_58591"),
    tenant_id=TenantId("t"),
    forme_juridique="SASU",
    regime_imposition="IS",
    regime_tva="reel_normal",
    nom="JAC TRANSPORTS",
    tva_recettes_regime="assujetti_taux_reduit",
    exercice_debut=date(2026, 1, 1),
    exercice_fin=date(2026, 12, 31),
)


def _fiche(
    nature: str | None = "5710",
    naf: str | None = "49.32Z",
    etat: str | None = "A",
    creation: date | None = date(2017, 12, 4),
) -> FicheSirene:
    return FicheSirene("102473030", nature, naf, etat, creation)


def test_la_reponse_de_l_api_devient_une_fiche() -> None:
    reponse = {
        "results": [
            {
                "siren": "102473030",
                "nature_juridique": "5710",
                "activite_principale": "49.32Z",
                "etat_administratif": "A",
                "date_creation": "2026-03-13",
            }
        ]
    }
    fiche = fiche_depuis_reponse(reponse, "102473030")
    assert fiche == FicheSirene("102473030", "5710", "49.32Z", "A", date(2026, 3, 13))
    assert fiche is not None and fiche.chauffeur and fiche.active


@pytest.mark.parametrize(
    "reponse",
    [{}, {"results": []}, {"results": [{"siren": "999999999"}]}, {"results": "x"}],
)
def test_une_reponse_qui_ne_vise_pas_ce_siren_ne_donne_rien(reponse: dict[str, object]) -> None:
    assert fiche_depuis_reponse(reponse, "102473030") is None


def test_une_valeur_illisible_devient_none() -> None:
    fiche = fiche_depuis_reponse(
        {
            "results": [
                {"siren": "102473030", "date_creation": "pas une date", "nature_juridique": 3}
            ]
        },
        "102473030",
    )
    assert fiche is not None
    assert (fiche.date_creation, fiche.nature_juridique) == (None, None)


def test_naf_et_etat() -> None:
    assert not _fiche(naf="70.22Z").chauffeur  # SERENITY GROUPE
    assert _fiche(naf="49.39B").chauffeur
    assert not _fiche(etat="C").active
    assert _fiche(etat=None).active


def test_formes_ambigues_et_sures() -> None:
    assert forme_depuis_nature("5710") == "SAS"
    assert forme_depuis_nature("5720") == "SASU"
    assert forme_depuis_nature("5499") == "SARL"
    assert forme_depuis_nature("1000") == "EI"
    assert forme_depuis_nature("9999") is None
    assert forme_depuis_nature(None) is None


def test_societe_creee_dans_l_annee_premier_exercice_a_sa_creation() -> None:
    """JAC TRANSPORTS, créée le 13/03/2026."""
    dossier = configurer_depuis_sirene(DOSSIER, _fiche(creation=date(2026, 3, 13)), AUJOURD_HUI)
    assert dossier.exercice_debut == date(2026, 3, 13)
    assert dossier.exercice_fin == date(2026, 12, 31)
    assert dossier.forme_juridique == "SAS"
    assert dossier.code_naf == "49.32Z"
    assert dossier.a_confirmer == ("exercice", "forme_juridique")
    configuration_de(dossier)  # la matrice l'accepte


def test_une_societe_ancienne_garde_son_exercice() -> None:
    dossier = configurer_depuis_sirene(DOSSIER, _fiche(nature="5720"), AUJOURD_HUI)
    assert (dossier.exercice_debut, dossier.exercice_fin) == (date(2026, 1, 1), date(2026, 12, 31))
    assert dossier.forme_juridique == "SASU"
    assert dossier.a_confirmer == ()


def test_un_exercice_deja_juste_n_est_jamais_deplace() -> None:
    choisi = configurer_depuis_sirene(DOSSIER, _fiche(creation=date(2026, 3, 13)), AUJOURD_HUI)
    rejoue = configurer_depuis_sirene(choisi, _fiche(creation=date(2026, 3, 13)), AUJOURD_HUI)
    assert rejoue == choisi


def test_une_date_de_creation_future_est_ignoree() -> None:
    dossier = configurer_depuis_sirene(DOSSIER, _fiche(creation=date(2027, 1, 2)), AUJOURD_HUI)
    assert dossier.exercice_debut == date(2026, 1, 1)
    assert "exercice" not in dossier.a_confirmer


def test_sans_nature_la_forme_reste_et_est_a_confirmer() -> None:
    dossier = configurer_depuis_sirene(DOSSIER, _fiche(nature=None), AUJOURD_HUI)
    assert dossier.forme_juridique == "SASU"
    assert "forme_juridique" in dossier.a_confirmer
