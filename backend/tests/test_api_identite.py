"""AXE-846 : le dirigeant saisit le siège, le capital et les associés de sa
société ; la liasse n'attend plus que ça."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_dossiers, get_lire_fiche_officielle, get_lire_registre
from axelcompta.core.ids import DossierId
from axelcompta.demo_identites import IDENTITE_KARIM
from axelcompta.tenants.identite_json import identite_vers_json
from axelcompta.tenants.registres import FicheOfficielle, PersonneOfficielle
from tests.tenants.test_identite_saisie import REPONSE_REGISTRE
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = "DEMO_karim"


def _client_sans_identite() -> TestClient:
    """Karim comme les 13 dossiers réels : une société sans identité."""
    client = _client()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    dossier = depot.obtenir(DossierId(KARIM))
    depot.reconfigurer_depuis_sirene(dataclasses.replace(dossier, identite=None, a_confirmer=()))
    client.app.dependency_overrides[get_lire_registre] = (  # type: ignore[attr-defined]
        lambda: lambda siren: REPONSE_REGISTRE
    )
    client.app.dependency_overrides[get_lire_fiche_officielle] = lambda: None  # type: ignore[attr-defined]
    return client


def _saisie(client: TestClient) -> dict[str, Any]:
    corps = identite_vers_json(IDENTITE_KARIM)
    assert corps is not None
    return corps


def test_sans_identite_la_liasse_est_refusee_et_le_formulaire_est_vide() -> None:
    client = _client_sans_identite()
    vue = client.get(f"/dossiers/{KARIM}/identite", headers=_en_tete(KARIM)).json()
    assert vue["identite"] is None
    assert (vue["associe_unique"], vue["qualite_par_defaut"]) == (True, "Président")
    liasse = client.get(f"/dossiers/{KARIM}/liasse-fiscale.pdf", headers=_en_tete(KARIM))
    assert liasse.status_code == 409
    assert "l'adresse du siège" in liasse.json()["detail"]


def test_le_registre_pre_remplit_depuis_le_siren() -> None:
    reponse = _client_sans_identite().get(
        f"/dossiers/{KARIM}/identite/registre",
        params={"siren": "987 142 031"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["nic"] == "00010"
    assert reponse.json()["adresse_siege"]["commune"] == "PARIS"
    assert reponse.json()["capital_social_cts"] is None
    assert reponse.json()["personnes"] == []


def test_le_rne_complete_le_capital_et_le_dirigeant() -> None:
    client = _client_sans_identite()
    fiche = FicheOfficielle(
        siren="987142031",
        lu_le=date(2026, 11, 11),
        sources=("rne",),
        capital_cts=10000,
        personnes=(PersonneOfficielle("REICHARD", "Arthur", "92160", "ANTONY"),),
    )

    def lire_fiche(_siren: str) -> FicheOfficielle:
        return fiche

    client.app.dependency_overrides[get_lire_fiche_officielle] = (  # type: ignore[attr-defined]
        lambda: lire_fiche
    )
    reponse = client.get(
        f"/dossiers/{KARIM}/identite/registre",
        params={"siren": "987142031"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert (corps["nic"], corps["capital_social_cts"]) == ("00010", 10000)
    assert corps["personnes"] == [
        {
            "nom": "REICHARD",
            "prenoms": "Arthur",
            "code_postal": "92160",
            "commune": "ANTONY",
            "pays": "France",
        }
    ]


def test_un_siren_faux_ou_inconnu_ne_pre_remplit_rien() -> None:
    client = _client_sans_identite()
    faux = client.get(
        f"/dossiers/{KARIM}/identite/registre", params={"siren": "123"}, headers=_en_tete(KARIM)
    )
    assert faux.status_code == 422
    inconnu = client.get(
        f"/dossiers/{KARIM}/identite/registre",
        params={"siren": "732829320"},
        headers=_en_tete(KARIM),
    )
    assert inconnu.status_code == 404


def test_saisir_l_identite_debloque_la_liasse_et_se_trace() -> None:
    client = _client_sans_identite()
    reponse = client.put(
        f"/dossiers/{KARIM}/identite", json=_saisie(client), headers=_en_tete(KARIM)
    )
    assert reponse.status_code == 200, reponse.text
    assert (reponse.json()["identite_manquante"], reponse.json()["raison_blocage"]) == ([], None)
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    assert [s[0] for s in depot.identites_saisies] == [KARIM]
    relue = client.get(f"/dossiers/{KARIM}/identite", headers=_en_tete(KARIM)).json()
    assert relue["identite"]["siren"] == "987142031"
    cloture = client.get(f"/dossiers/{KARIM}/cloture-exercice", headers=_en_tete(KARIM)).json()
    assert cloture.get("code") != "configuration"


def test_une_saisie_invalide_est_refusee_avec_sa_phrase() -> None:
    client = _client_sans_identite()
    corps: dict[str, Any] = {**_saisie(client), "capital_social_cts": 0}
    reponse = client.put(f"/dossiers/{KARIM}/identite", json=corps, headers=_en_tete(KARIM))
    assert reponse.status_code == 422
    assert "capital" in reponse.json()["detail"]
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    assert depot.identites_saisies == []


def test_un_autre_chauffeur_ne_lit_ni_ne_saisit_cette_identite() -> None:
    client = _client_sans_identite()
    autre = _en_tete("DEMO_sophie")
    assert client.get(f"/dossiers/{KARIM}/identite", headers=autre).status_code in (403, 404)
    saisie: Mapping[str, Any] = _saisie(client)
    put = client.put(f"/dossiers/{KARIM}/identite", json=saisie, headers=autre)
    assert put.status_code in (403, 404)
