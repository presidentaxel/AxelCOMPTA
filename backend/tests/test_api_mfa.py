"""AXE-812 : double authentification (MFA native de Supabase) et traces
d'accès (connexions, exports)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from axelcompta.core.ids import DossierId
from axelcompta.demo_api import (
    MESSAGE_MFA_REQUISE,
    get_comptes,
    get_journal_acces,
    get_journal_portefeuille,
)
from axelcompta.demo_comptes_memory import InMemoryCompteRepository
from axelcompta.tenants.journal_portefeuille import (
    ACTE_CONNEXION_MEMBRE,
    ACTE_MFA_REINITIALISEE,
    JournalPortefeuilleMemoire,
)
from axelcompta.workflow.journal_acces import JournalAccesMemoire
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)


def _surcharge(client: TestClient, dependance: object) -> object:
    return client.app.dependency_overrides[dependance]()  # type: ignore[attr-defined]


def test_un_admin_sans_code_ne_voit_que_l_ecran_d_enrolement() -> None:
    """Critère du ticket : l'admin connecté au mot de passe seul (`aal1`)."""
    client = _client()
    sans_code = _en_tete_gestionnaire(aal="aal1")

    portefeuille = client.get("/dossiers", headers=sans_code)
    moi = client.get("/portefeuille/moi", headers=sans_code)
    connexion = client.post("/session/connexion", headers=sans_code)

    assert portefeuille.status_code == 403
    assert portefeuille.json()["detail"] == MESSAGE_MFA_REQUISE
    assert moi.status_code == 200
    assert (moi.json()["role"], moi.json()["mfa_requise"], moi.json()["aal"]) == (
        "admin",
        True,
        "aal1",
    )
    assert connexion.status_code == 204


def test_avec_le_code_l_admin_ouvre_le_portefeuille() -> None:
    client = _client()
    assert client.get("/dossiers", headers=_en_tete_gestionnaire()).status_code == 200
    moi = client.get("/portefeuille/moi", headers=_en_tete_gestionnaire()).json()
    assert moi["mfa_requise"] is False


def test_un_membre_et_un_chauffeur_n_ont_pas_l_obligation() -> None:
    """Proposée aux autres rôles et au chauffeur, pas imposée."""
    client = _client_et_stubs(role="membre")[0]
    assert client.get("/dossiers", headers=_en_tete_gestionnaire(aal="aal1")).status_code == 200
    chauffeur = _client()
    assert chauffeur.get("/dossiers/DEMO_karim", headers=_en_tete("DEMO_karim")).status_code == 200


def test_un_telechargement_du_fec_est_trace_et_visible_du_dirigeant() -> None:
    """Critère du ticket : une ligne au journal d'audit par téléchargement."""
    client = _client()
    en_tete = _en_tete("DEMO_karim")

    assert client.get("/dossiers/DEMO_karim/fec.txt", headers=en_tete).status_code == 200
    assert client.get("/dossiers/DEMO_karim/balance.csv", headers=en_tete).status_code == 200

    journal = _surcharge(client, get_journal_acces)
    assert isinstance(journal, JournalAccesMemoire)
    exports = [(str(d), a.type_acte) for d, a in journal.actes]
    assert exports == [("DEMO_karim", "export"), ("DEMO_karim", "export")]
    acces = client.get("/dossiers/DEMO_karim/acces", headers=en_tete).json()
    assert {a["reference"] for a in acces} >= {"balance-DEMO_karim.csv"}
    assert all(a["par_vous"] for a in acces)


def test_un_export_refuse_ne_laisse_pas_de_trace() -> None:
    client = _client()
    autre = client.get("/dossiers/DEMO_sophie/fec.txt", headers=_en_tete("DEMO_karim"))
    assert autre.status_code == 403
    journal = _surcharge(client, get_journal_acces)
    assert isinstance(journal, JournalAccesMemoire)
    assert journal.actes == []


def test_la_connexion_est_tracee_cote_dossier_et_cote_portefeuille() -> None:
    client = _client()
    client.post("/session/connexion", headers=_en_tete("DEMO_karim"))
    client.post("/session/connexion", headers=_en_tete_gestionnaire())

    acces = _surcharge(client, get_journal_acces)
    portefeuille = _surcharge(client, get_journal_portefeuille)
    assert isinstance(acces, JournalAccesMemoire)
    assert isinstance(portefeuille, JournalPortefeuilleMemoire)
    assert [(d, a.type_acte) for d, a in acces.actes] == [(DossierId("DEMO_karim"), "connexion")]
    assert [a.type_acte for a in portefeuille.actes] == [ACTE_CONNEXION_MEMBRE]
    assert client.post("/session/connexion").status_code == 401


def _client_avec_membre(role: str = "admin") -> tuple[TestClient, InMemoryCompteRepository]:
    client = _client_et_stubs(role=role)[0]
    comptes = _surcharge(client, get_comptes)
    assert isinstance(comptes, InMemoryCompteRepository)
    comptes.inviter_membre("TENANT_DEMO", "collegue@example.com")
    comptes.facteurs_mfa[("TENANT_DEMO", "collegue@example.com")] = 1
    return client, comptes


def test_un_autre_admin_reinitialise_la_mfa_et_c_est_trace() -> None:
    client, comptes = _client_avec_membre()
    url = "/portefeuille/membres/collegue@example.com/mfa/reinitialiser"

    reponse = client.post(url, headers=_en_tete_gestionnaire())

    assert reponse.status_code == 200
    assert reponse.json() == {"facteurs_retires": 1}
    assert comptes.facteurs_mfa == {}
    portefeuille = _surcharge(client, get_journal_portefeuille)
    assert isinstance(portefeuille, JournalPortefeuilleMemoire)
    (acte,) = portefeuille.actes
    assert (acte.type_acte, acte.reference) == (ACTE_MFA_REINITIALISEE, "collegue@example.com")


def test_on_ne_reinitialise_ni_la_sienne_ni_sans_etre_admin() -> None:
    client, _ = _client_avec_membre()
    soi = client.post(
        "/portefeuille/membres/gestionnaire@example.com/mfa/reinitialiser",
        headers=_en_tete_gestionnaire(),
    )
    inconnu = client.post(
        "/portefeuille/membres/personne@example.com/mfa/reinitialiser",
        headers=_en_tete_gestionnaire(),
    )
    membre, _ = _client_avec_membre(role="membre")
    refuse = membre.post(
        "/portefeuille/membres/collegue@example.com/mfa/reinitialiser",
        headers=_en_tete_gestionnaire(),
    )
    assert (soi.status_code, inconnu.status_code, refuse.status_code) == (409, 404, 403)
