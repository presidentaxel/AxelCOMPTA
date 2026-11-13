"""Vue « déjà classées » du mode expert (AXE-823)."""

from __future__ import annotations

from axelcompta.api.routes import get_cache_classees
from axelcompta.core.ids import DossierId
from axelcompta.workflow.classees_cache import VERSION_CLASSEES
from axelcompta.workflow.file_expert_cache import SujetsGardes
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _client_expert,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

EN_TETE = _en_tete_gestionnaire()


def test_les_classees_sont_filtrees_paginees_et_comptees() -> None:
    client = _client_expert()
    corps = client.get("/expert/classees", headers=EN_TETE).json()
    assert corps["total"] > 0 and corps["operations"]
    assert len(corps["operations"]) <= 50
    assert corps["compteurs"]["auto"] > 0

    regles = client.get(
        "/expert/classees", params={"statut": "auto", "origine": "regle"}, headers=EN_TETE
    ).json()
    assert regles["operations"]
    assert {o["origine"] for o in regles["operations"]} == {"regle"}
    assert all(o["compte"] != "471" for o in regles["operations"])


def test_le_tri_par_confiance_met_les_plus_fragiles_en_premier() -> None:
    corps = (
        _client_expert()
        .get("/expert/classees", params={"statut": "auto", "tri": "confiance"}, headers=EN_TETE)
        .json()
    )
    confiances = [o["confiance"] for o in corps["operations"] if o["confiance"] is not None]
    assert confiances == sorted(confiances)


def test_un_verdict_juste_est_garde_et_compte() -> None:
    client = _client_expert()
    premiere = client.get("/expert/classees", headers=EN_TETE).json()["operations"][0]
    reponse = client.post(
        "/expert/classees/verdict",
        json={
            "dossier_id": premiere["dossier_id"],
            "ecriture_id": premiere["ecriture_id"],
            "verdict": "juste",
        },
        headers=EN_TETE,
    )
    assert reponse.status_code == 204
    relu = client.get("/expert/classees", headers=EN_TETE).json()
    assert relu["compteurs"]["justes"] == 1
    assert relu["operations"][0]["verdict"] == "juste"


def test_la_lecture_ne_note_pas_et_un_autre_portefeuille_est_introuvable() -> None:
    lecture = _client_et_stubs("lecture")[0]
    entree = {"dossier_id": "DEMO_karim", "ecriture_id": "x", "verdict": "faux"}
    assert lecture.post("/expert/classees/verdict", json=entree, headers=EN_TETE).status_code == 403
    autre = _en_tete_gestionnaire(tenant_id="AUTRE_TENANT")
    # AXE-800 : l'expert n'est habilité que sur son portefeuille.
    assert (
        _client_expert().post("/expert/classees/verdict", json=entree, headers=autre).status_code
        == 403
    )


class _CacheCompte:
    """Garde les opérations et compte les recalculs."""

    def __init__(self) -> None:
        self._gardes: dict[DossierId, SujetsGardes] = {}
        self.ecritures = 0

    def lire(self, dossier_ids: list[DossierId]) -> dict[DossierId, SujetsGardes]:
        return {
            dossier_id: self._gardes[dossier_id]
            for dossier_id in dossier_ids
            if dossier_id in self._gardes
        }

    def enregistrer(
        self, dossier_id: DossierId, version_source: int, sujets: list[dict[str, object]]
    ) -> None:
        self.ecritures += 1
        self._gardes[dossier_id] = SujetsGardes(version_source, VERSION_CLASSEES, sujets)


def test_changer_de_filtre_ne_recalcule_pas_et_le_verdict_est_relu() -> None:
    """AXE-824 : un filtre relit le cache. Un verdict, qui n'écrit pas,
    apparaît quand même au prochain affichage."""
    client = _client_expert()
    cache = _CacheCompte()
    client.app.dependency_overrides[get_cache_classees] = lambda: cache  # type: ignore[attr-defined]
    premiere = client.get("/expert/classees", headers=EN_TETE).json()["operations"][0]
    ecrits = cache.ecritures
    assert ecrits > 0

    client.get("/expert/classees", params={"statut": "chauffeur"}, headers=EN_TETE)
    assert cache.ecritures == ecrits

    reponse = client.post(
        "/expert/classees/verdict",
        json={
            "dossier_id": premiere["dossier_id"],
            "ecriture_id": premiere["ecriture_id"],
            "verdict": "faux",
        },
        headers=EN_TETE,
    )
    assert reponse.status_code == 204
    relu = client.get("/expert/classees", headers=EN_TETE).json()
    assert cache.ecritures == ecrits
    trouve = next(o for o in relu["operations"] if o["ecriture_id"] == premiere["ecriture_id"])
    assert trouve["verdict"] == "faux"
