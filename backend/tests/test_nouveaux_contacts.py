"""AXE-845 : repérer et préparer les contacts Digifactory sans dossier."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from axelcompta.nouveaux_contacts import (
    contacts_sans_dossier,
    fiche_sirene,
    id_du_dossier,
    proposer,
)
from axelcompta.tenants.sirene import FicheSirene

AUJOURD_HUI = date(2026, 11, 6)


def test_contacts_sans_dossier_ecarte_les_connus_et_les_numeros_illisibles() -> None:
    contacts: dict[str, dict[str, object]] = {
        "3": {"nr": 3},
        "10": {"nr": 10},
        "x": {"nr": "abc"},
        "2": {"nr": 2},
    }
    retenus = contacts_sans_dossier(contacts, {"3"})
    assert [c["nr"] for c in retenus] == [2, 10]  # ordre numérique


def test_proposer_prepare_depuis_sirene() -> None:
    fiche = FicheSirene("111111111", "5710", "49.32Z", "A", date(2026, 3, 13))
    proposition = proposer(
        {"nr": 10, "companyName": "VTC NORD", "siren": "111111111"},
        lambda siren: fiche if siren == "111111111" else None,
        AUJOURD_HUI,
    )
    assert (proposition.contact_nr, proposition.nom) == ("10", "VTC NORD")
    assert proposition.chauffeur
    assert proposition.dossier is not None and proposition.dossier.exercice_debut == date(
        2026, 3, 13
    )
    assert id_du_dossier("10") == "DIGI_10"


def test_sans_fiche_tout_est_a_confirmer_et_ce_n_est_pas_evident() -> None:
    proposition = proposer({"nr": 11, "companyName": "INCONNUE"}, lambda _s: None, AUJOURD_HUI)
    assert proposition.dossier is not None
    assert not proposition.chauffeur
    assert proposition.avertissements == ("pas de fiche Sirene",)


def test_fiche_sirene_lit_la_reponse(monkeypatch: pytest.MonkeyPatch) -> None:
    assert fiche_sirene(None) is None

    def repondre(*_args: object, **_kwargs: object) -> httpx.Response:
        corps = {
            "results": [
                {
                    "siren": "111111111",
                    "nature_juridique": "5710",
                    "activite_principale": "49.32Z",
                    "etat_administratif": "A",
                    "date_creation": "2026-03-13",
                }
            ]
        }
        return httpx.Response(200, json=corps, request=httpx.Request("GET", "https://x"))

    monkeypatch.setattr(httpx, "get", repondre)
    fiche = fiche_sirene("111111111")
    assert fiche is not None and fiche.code_naf == "49.32Z"
