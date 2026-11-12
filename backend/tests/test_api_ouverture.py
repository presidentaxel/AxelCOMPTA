"""AXE-804 : le dirigeant, ou l'expert-comptable habilité, reprend le bilan
d'ouverture depuis le FEC de l'outil précédent ; un faux est refusé."""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from axelcompta.closing.ouverture import id_a_nouveaux
from axelcompta.closing.ouverture_depot import OuverturesMemoire
from axelcompta.core.ids import DossierId
from axelcompta.demo_api import get_dossiers, get_experts, get_ledger, get_ouvertures
from axelcompta.demo_identites import IDENTITE_KARIM
from tests.closing.fec_externe import ECRITURES, NOM, fec
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _client_expert,
    _en_tete,
    _en_tete_gestionnaire,
    _expert_habilite,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = "DEMO_karim"
REPRISE = "DEMO_reprise"


def _avec_dossier_a_reprendre(client: TestClient) -> OuverturesMemoire:
    """Une société existante qui arrive au 1er janvier 2026, sans écriture."""
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    karim = depot.obtenir(DossierId(KARIM))
    depot.enregistrer(
        dataclasses.replace(
            karim,
            id=DossierId(REPRISE),
            contact_nr=None,
            identite=IDENTITE_KARIM,
            exercice_debut=date(2026, 1, 1),
            exercice_fin=date(2026, 12, 31),
            a_confirmer=(),
        )
    )
    ledger = client.app.dependency_overrides[get_ledger]()  # type: ignore[attr-defined]
    ouvertures = OuverturesMemoire(ledger, depot)
    client.app.dependency_overrides[get_ouvertures] = lambda: ouvertures  # type: ignore[attr-defined]
    return ouvertures


def _fichier(texte: str | None = None, nom: str = NOM) -> dict[str, Any]:
    return {"fichier": (nom, (texte or fec()).encode(), "text/plain")}


def test_le_dirigeant_analyse_puis_reprend_son_bilan_d_ouverture() -> None:
    client = _client()
    ouvertures = _avec_dossier_a_reprendre(client)
    entete = _en_tete(REPRISE)
    analyse = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec/analyse", files=_fichier(), headers=entete
    )
    assert analyse.status_code == 200, analyse.text
    corps = analyse.json()
    assert corps["possible"] is True
    assert {"compte": "120", "debit_cts": 0, "credit_cts": 3000000} in corps["a_nouveaux"]
    reprise = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(),
        data={"attestation": corps["attestation"], "deficits_euros": "2500"},
        headers=entete,
    )
    assert reprise.status_code == 200, reprise.text
    assert reprise.json()["faite"] is True
    ledger = client.app.dependency_overrides[get_ledger]()  # type: ignore[attr-defined]
    ids = {e.id for e in ledger.grand_livre(DossierId(REPRISE))}
    assert id_a_nouveaux(DossierId(REPRISE), 2026) in ids
    importee = ouvertures.obtenir(DossierId(REPRISE))
    assert importee is not None and (importee.role, importee.deficits_euros) == ("dirigeant", 2500)
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    assert depot.obtenir(DossierId(REPRISE)).deficits_anterieurs_euros == 2500
    # Verrouillée : une seconde reprise est refusée.
    encore = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(),
        data={"attestation": corps["attestation"]},
        headers=entete,
    )
    assert encore.status_code == 422
    assert "déjà repris" in encore.json()["detail"]


def test_un_fec_desequilibre_est_refuse_avec_sa_raison() -> None:
    client = _client()
    _avec_dossier_a_reprendre(client)
    faux = [*ECRITURES[:-1], ("AC", "AC0001", "20250915", "51200000", "0,00", "1,00")]
    analyse = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec/analyse",
        files=_fichier(fec(faux)),
        headers=_en_tete(REPRISE),
    ).json()
    assert analyse["possible"] is False
    assert any("déséquilibrée" in r for r in analyse["refus"])
    reprise = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(fec(faux)),
        data={"attestation": analyse["attestation"]},
        headers=_en_tete(REPRISE),
    )
    assert reprise.status_code == 422


def test_sans_l_attestation_exacte_rien_n_est_repris() -> None:
    client = _client()
    ouvertures = _avec_dossier_a_reprendre(client)
    reprise = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(),
        data={"attestation": "oui"},
        headers=_en_tete(REPRISE),
    )
    assert reprise.status_code == 422
    assert ouvertures.obtenir(DossierId(REPRISE)) is None


def test_un_compte_inconnu_se_fait_correspondre() -> None:
    client = _client()
    _avec_dossier_a_reprendre(client)
    lignes = [lg if lg[3] != "60610000" else (*lg[:3], "CARBU", *lg[4:]) for lg in ECRITURES]
    analyse = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec/analyse",
        files=_fichier(fec(lignes)),
        data={"correspondance": '{"CARBU": "6061"}'},
        headers=_en_tete(REPRISE),
    ).json()
    assert analyse["possible"] is True


def test_un_autre_chauffeur_ne_reprend_pas_ce_dossier() -> None:
    client = _client()
    _avec_dossier_a_reprendre(client)
    reponse = client.post(
        f"/dossiers/{REPRISE}/ouverture/fec/analyse", files=_fichier(), headers=_en_tete(KARIM)
    )
    assert reponse.status_code in (403, 404)


def test_l_expert_habilite_reprend_avec_un_motif() -> None:
    client = _client_expert()
    ouvertures = _avec_dossier_a_reprendre(client)
    entete = _en_tete_gestionnaire()
    analyse = client.post(
        f"/expert/dossiers/{REPRISE}/ouverture/fec/analyse", files=_fichier(), headers=entete
    )
    # Le dossier de reprise n'est pas dans la lettre de mission de l'expert.
    assert analyse.status_code == 403

    experts = client.app.dependency_overrides[get_experts]()  # type: ignore[attr-defined]
    experts.habilitations.clear()
    _expert_habilite(experts, dossiers=(DossierId(REPRISE),))
    analyse = client.post(
        f"/expert/dossiers/{REPRISE}/ouverture/fec/analyse", files=_fichier(), headers=entete
    ).json()
    sans_motif = client.post(
        f"/expert/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(),
        data={"attestation": analyse["attestation"], "motif": " "},
        headers=entete,
    )
    assert sans_motif.status_code == 422
    reprise = client.post(
        f"/expert/dossiers/{REPRISE}/ouverture/fec",
        files=_fichier(),
        data={
            "attestation": analyse["attestation"],
            "motif": "Reprise du FEC du cabinet précédent",
        },
        headers=entete,
    )
    assert reprise.status_code == 200, reprise.text
    importee = ouvertures.obtenir(DossierId(REPRISE))
    assert importee is not None
    assert (importee.role, importee.auteur_nom) == ("expert_comptable", "Claire Expert")
