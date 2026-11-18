"""AXE-832 : comptes bancaires d'un dossier côté API (route, vue, FEC)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from httpx import Response

from axelcompta.api.routes import (
    get_comptes_bancaires,
    get_demandes_jobs,
    get_dossiers,
    get_experts,
    get_fiches_import,
    get_ledger,
    get_notifications,
    libelles_banques,
    vues_comptes_bancaires,
)
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaire,
    CompteBancaireMemoire,
    CompteReleve,
    relever_comptes,
)
from axelcompta.jobs.file import FileMemoire
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.service import LedgerService
from axelcompta.tenants.fiches_import import FicheImport
from axelcompta.workflow.expert_comptable import ROLE_EXPERT
from axelcompta.workflow.notifications import notifier_comptes_a_choisir
from tests.test_demo_api import (  # noqa: F401 — fixtures autouse réutilisées
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
    _expert_habilite,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = DossierId("DEMO_karim")
LE = datetime(2026, 11, 5, 4, 0, tzinfo=UTC)


def _ecriture(id_: str, banque: str, montant: int) -> Ecriture:
    sens_banque = Sens.DEBIT if montant > 0 else Sens.CREDIT
    autre = Sens.CREDIT if sens_banque is Sens.DEBIT else Sens.DEBIT
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=KARIM,
        journal=Journal.BQ,
        date=date(2025, 6, 1),
        libelle="TOTAL",
        reference_piece=None,
        lignes=(
            LigneEcriture(banque, sens_banque, Money(abs(montant))),
            LigneEcriture("6061", autre, Money(abs(montant))),
        ),
    )


def test_la_vue_met_les_deux_soldes_cote_a_cote() -> None:
    comptes = (
        CompteBancaire(KARIM, "pro", "5121", "Compte PRO", 4_000, LE, retenu=True),
        CompteBancaire(KARIM, "fiscal", "5122", None),
    )
    ecritures = (
        _ecriture("a", "5121", 10_000),
        _ecriture("b", "5121", -6_000),
        _ecriture("c", "512", -1_500),
    )
    vues = {v.compte: v for v in vues_comptes_bancaires(comptes, ecritures)}
    assert vues["5121"].solde_comptable_cts == 4_000
    assert vues["5121"].solde_banque_cts == 4_000
    assert vues["5121"].ecart_cts == 0
    assert vues["5121"].releve_le == LE.isoformat()
    assert vues["5122"].solde_comptable_cts == 0
    assert vues["5122"].ecart_cts is None  # jamais relevé
    assert vues["512"].solde_comptable_cts == -1_500  # non ventilé, affiché à part


def test_un_512_a_zero_n_est_pas_affiche() -> None:
    vues = vues_comptes_bancaires((), (_ecriture("a", "512", 100), _ecriture("b", "512", -100)))
    assert vues == []


def test_le_libelle_fec_reprend_le_nom_du_compte() -> None:
    comptes = (
        CompteBancaire(KARIM, "pro", "5121", "Compte PRO"),
        CompteBancaire(KARIM, "x", "5122", None),
    )
    assert libelles_banques(comptes) == {"5121": "Banque — Compte PRO"}


def test_la_route_et_le_fec_montrent_les_sous_comptes() -> None:
    client = _client_et_stubs()[0]
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    ledger: LedgerService = overrides[get_ledger]()
    comptes: CompteBancaireMemoire = overrides[get_comptes_bancaires]()
    relever_comptes(comptes, KARIM, [CompteReleve("pro", "Compte PRO", 2_500)], LE)
    ledger.enregistrer(_ecriture("DEMO_karim:ventile", "5121", 2_500))

    reponse = client.get("/dossiers/DEMO_karim/comptes-bancaires", headers=_en_tete("DEMO_karim"))

    assert reponse.status_code == 200
    par_compte = {c["compte"]: c for c in reponse.json()}
    assert par_compte["5121"]["nom"] == "Compte PRO"
    assert par_compte["5121"]["ecart_cts"] == 0
    fec = client.get("/dossiers/DEMO_karim/fec.txt", headers=_en_tete("DEMO_karim")).text
    assert "5121\tBanque — Compte PRO" in fec


def test_le_gestionnaire_ne_voit_pas_les_soldes() -> None:
    client = _client_et_stubs()[0]
    url = "/dossiers/DEMO_karim/comptes-bancaires"
    assert client.get(url, headers=_en_tete_gestionnaire()).status_code == 403
    assert client.get(url, headers=_en_tete("DEMO_sophie")).status_code == 403
    assert client.get(url).status_code == 401


def _client_pro_et_perso() -> tuple[TestClient, CompteBancaireMemoire]:
    """Karim : compte pro (retenu, une écriture) et livret perso (à décider)."""
    client = _client_et_stubs()[0]
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    comptes: CompteBancaireMemoire = overrides[get_comptes_bancaires]()
    releves = [CompteReleve("pro", "Compte PRO", 2_500), CompteReleve("perso", "Livret", 90_000)]
    relever_comptes(comptes, KARIM, releves, LE)
    comptes.decider(KARIM, "5121", True, UserId("karim"), LE)
    overrides[get_ledger]().enregistrer(_ecriture("DEMO_karim:ventile", "5121", 2_500))
    return client, comptes


def _decider(client: TestClient, compte: str, retenu: bool) -> Response:
    reponse: Response = client.post(
        f"/dossiers/DEMO_karim/comptes-bancaires/{compte}/decision",
        json={"retenu": retenu},
        headers=_en_tete("DEMO_karim"),
    )
    return reponse


def test_un_compte_a_decider_n_affiche_pas_d_ecart() -> None:
    client, _ = _client_pro_et_perso()
    vues = client.get(
        "/dossiers/DEMO_karim/comptes-bancaires", headers=_en_tete("DEMO_karim")
    ).json()
    livret = next(v for v in vues if v["compte"] == "5122")
    assert (livret["retenu"], livret["ecart_cts"]) == (None, None)


def test_le_dirigeant_ecarte_son_livret_et_c_est_trace() -> None:
    client, comptes = _client_pro_et_perso()
    reponse = _decider(client, "5122", False)
    assert reponse.status_code == 200
    assert next(v for v in reponse.json() if v["compte"] == "5122")["retenu"] is False
    assert [(d[1], d[2]) for d in comptes.decisions] == [("5121", True), ("5122", False)]


def test_retenir_apres_coup_demande_une_relecture() -> None:
    client, comptes = _client_pro_et_perso()
    assert _decider(client, "5122", True).status_code == 200
    livret = next(c for c in comptes.lister(KARIM) if c.compte_comptable == "5122")
    assert (livret.retenu, livret.a_relire) == (True, True)


def test_un_compte_deja_comptabilise_ne_s_ecarte_pas() -> None:
    client, _ = _client_pro_et_perso()
    reponse = _decider(client, "5121", False)
    assert reponse.status_code == 409
    assert "déjà dans la comptabilité" in reponse.json()["detail"]


def test_un_compte_inconnu_repond_404() -> None:
    client, _ = _client_pro_et_perso()
    assert _decider(client, "5129", True).status_code == 404


def test_seul_le_dirigeant_decide() -> None:
    client, _ = _client_pro_et_perso()
    reponse = client.post(
        "/dossiers/DEMO_karim/comptes-bancaires/5122/decision",
        json={"retenu": True},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 403


def test_le_gestionnaire_voit_combien_de_comptes_attendent_un_choix() -> None:
    """AXE-851 : un nombre, une date et les opérations retenues, sans le
    nom ni le solde des comptes (doc 19 §2.4)."""
    client, comptes = _client_pro_et_perso()
    comptes.operations[(KARIM, "perso")] = 12

    reponse = client.get("/dossiers", headers=_en_tete_gestionnaire())

    par_dossier = {d["dossier_id"]: d for d in reponse.json()}
    karim = par_dossier["DEMO_karim"]
    assert (karim["comptes_a_choisir"], karim["operations_en_attente_de_choix"]) == (1, 12)
    assert karim["comptes_a_choisir_depuis"] is not None
    assert "Livret" not in reponse.text
    assert par_dossier["DEMO_sophie"]["comptes_a_choisir"] == 0
    _decider(client, "5122", False)
    apres = client.get("/dossiers", headers=_en_tete_gestionnaire()).json()
    assert {d["dossier_id"]: d["comptes_a_choisir"] for d in apres}["DEMO_karim"] == 0


def test_la_cloche_du_chauffeur_dit_combien_de_comptes_attendent() -> None:
    client, comptes = _client_pro_et_perso()
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    notifier_comptes_a_choisir(KARIM, 1, overrides[get_notifications](), datetime(2026, 11, 9))
    url = "/dossiers/DEMO_karim/notifications"

    messages = [n["message"] for n in client.get(url, headers=_en_tete("DEMO_karim")).json()]
    assert "Un compte bancaire attend votre choix : sert-il à votre activité ?" in messages

    _decider(client, "5122", False)
    messages = [n["message"] for n in client.get(url, headers=_en_tete("DEMO_karim")).json()]
    assert not any("attend votre choix" in m for m in messages)


def _client_expert_pro_et_perso(
    role: str = ROLE_EXPERT,
) -> tuple[TestClient, CompteBancaireMemoire]:
    """Même dossier que `_client_pro_et_perso`, vu depuis le portefeuille."""
    client = _client_et_stubs(role=role)[0]
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    comptes: CompteBancaireMemoire = overrides[get_comptes_bancaires]()
    releves = [CompteReleve("pro", "Compte PRO", 2_500), CompteReleve("perso", "Livret", 90_000)]
    relever_comptes(comptes, KARIM, releves, LE)
    comptes.decider(KARIM, "5121", True, UserId("karim"), LE)
    overrides[get_ledger]().enregistrer(_ecriture("DEMO_karim:ventile", "5121", 2_500))
    return client, comptes


def _decider_expert(client: TestClient, compte: str, retenu: bool) -> Response:
    reponse: Response = client.post(
        f"/expert/dossiers/DEMO_karim/comptes-bancaires/{compte}/decision",
        json={"retenu": retenu},
        headers=_en_tete_gestionnaire(),
    )
    return reponse


def test_l_expert_voit_les_comptes_du_dossier() -> None:
    """AXE-956 : l'expert habilité voit nom et état de chaque compte."""
    client, _ = _client_expert_pro_et_perso()
    reponse = client.get(
        "/expert/dossiers/DEMO_karim/comptes-bancaires", headers=_en_tete_gestionnaire()
    )
    assert reponse.status_code == 200
    par_compte = {c["compte"]: c for c in reponse.json()}
    assert (par_compte["5121"]["retenu"], par_compte["5122"]["retenu"]) == (True, None)
    assert par_compte["5122"]["nom"] == "Livret"


def test_l_expert_retient_un_compte_a_la_place_du_dirigeant() -> None:
    client, comptes = _client_expert_pro_et_perso()
    reponse = _decider_expert(client, "5122", True)
    assert reponse.status_code == 200
    livret = next(c for c in comptes.lister(KARIM) if c.compte_comptable == "5122")
    assert (livret.retenu, livret.a_relire) == (True, True)
    # Tracé au nom de l'expert, pas du dirigeant.
    assert comptes.decisions[-1][1:4] == ("5122", True, UserId("gestionnaire-1"))
    apres = client.get("/dossiers", headers=_en_tete_gestionnaire()).json()
    assert {d["dossier_id"]: d["comptes_a_choisir"] for d in apres}["DEMO_karim"] == 0


def test_l_expert_ecarte_un_compte_personnel() -> None:
    client, comptes = _client_expert_pro_et_perso()
    assert _decider_expert(client, "5122", False).status_code == 200
    assert comptes.decisions[-1][1:3] == ("5122", False)


def test_l_expert_n_ecarte_pas_un_compte_deja_comptabilise() -> None:
    client, _ = _client_expert_pro_et_perso()
    reponse = _decider_expert(client, "5121", False)
    assert reponse.status_code == 409
    assert "déjà dans la comptabilité" in reponse.json()["detail"]


def test_le_gestionnaire_non_expert_ne_decide_pas() -> None:
    client, comptes = _client_expert_pro_et_perso(role="admin")
    lecture = client.get(
        "/expert/dossiers/DEMO_karim/comptes-bancaires", headers=_en_tete_gestionnaire()
    )
    assert lecture.status_code == 403
    assert _decider_expert(client, "5122", True).status_code == 403
    assert [d[1] for d in comptes.decisions] == ["5121"]


def test_l_expert_hors_lettre_de_mission_ne_decide_pas() -> None:
    client, comptes = _client_expert_pro_et_perso()
    experts = client.app.dependency_overrides[get_experts]()  # type: ignore[attr-defined]
    experts.habilitations.clear()
    _expert_habilite(experts, dossiers=(DossierId("DEMO_sophie"),))
    assert _decider_expert(client, "5122", True).status_code == 403
    assert [d[1] for d in comptes.decisions] == ["5121"]


def _fiche_de_karim(client: TestClient) -> str:
    """AXE-986 : une fiche d'import reliée au dossier de Karim."""
    overrides = client.app.dependency_overrides  # type: ignore[attr-defined]
    dossier = overrides[get_dossiers]().obtenir(KARIM)
    fiche = FicheImport(
        "fiche-karim", dossier.tenant_id, "Dupont", "Karim", "admin@x", LE, dossier_id=KARIM
    )
    overrides[get_fiches_import]().enregistrer(fiche)
    file = FileMemoire()
    overrides[get_demandes_jobs] = lambda: file
    return fiche.id


def _choisir_sur_la_fiche(client: TestClient, fiche_id: str, usage: str) -> None:
    comptes = [{"id": "pro", "nom": "Compte PRO", "usage": "pro"}]
    comptes.append({"id": "perso", "nom": "Livret", "usage": usage})
    reponse = client.patch(
        f"/portefeuille/imports/{fiche_id}",
        json={"champs": {"comptes_bancaires": json.dumps(comptes)}},
        headers=_en_tete_gestionnaire(),
    )
    assert reponse.status_code == 200, reponse.text


def test_le_choix_de_l_expert_sur_la_fiche_passe_au_dossier() -> None:
    client, comptes = _client_expert_pro_et_perso()
    _choisir_sur_la_fiche(client, _fiche_de_karim(client), "perso")
    livret = next(c for c in comptes.lister(KARIM) if c.compte_comptable == "5122")
    assert livret.retenu is False
    assert comptes.decisions[-1][1:4] == ("5122", False, UserId("gestionnaire-1"))


def test_le_choix_d_un_gestionnaire_reste_une_proposition() -> None:
    """Enregistrée par quelqu'un qui n'est pas l'expert habilité sur ce
    dossier, la fiche propose ; l'expert le voit et confirme."""
    client, comptes = _client_expert_pro_et_perso()
    experts = client.app.dependency_overrides[get_experts]()  # type: ignore[attr-defined]
    experts.habilitations.clear()
    _choisir_sur_la_fiche(client, _fiche_de_karim(client), "perso")
    assert [d[1] for d in comptes.decisions] == ["5121"]  # rien de plus
    _expert_habilite(experts)
    vues = client.get(
        "/expert/dossiers/DEMO_karim/comptes-bancaires", headers=_en_tete_gestionnaire()
    ).json()
    par_compte = {v["compte"]: v for v in vues}
    assert (par_compte["5122"]["retenu"], par_compte["5122"]["propose_par_fiche"]) == (None, False)
    assert par_compte["5121"]["propose_par_fiche"] is True


def test_la_fiche_ne_change_jamais_un_compte_deja_decide() -> None:
    client, comptes = _client_expert_pro_et_perso()
    _choisir_sur_la_fiche(client, _fiche_de_karim(client), "perso")
    _decider_expert(client, "5122", True)
    _choisir_sur_la_fiche(client, "fiche-karim", "perso")
    livret = next(c for c in comptes.lister(KARIM) if c.compte_comptable == "5122")
    assert livret.retenu is True
