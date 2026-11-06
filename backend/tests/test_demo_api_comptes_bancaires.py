"""AXE-832 : comptes bancaires d'un dossier côté API (route, vue, FEC)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from httpx import Response

from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.demo_api import (
    get_comptes_bancaires,
    get_ledger,
    libelles_banques,
    vues_comptes_bancaires,
)
from axelcompta.ingestion.comptes_bancaires import (
    CompteBancaire,
    CompteBancaireMemoire,
    CompteReleve,
    relever_comptes,
)
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.ledger.service import LedgerService
from tests.test_demo_api import (  # noqa: F401 — fixtures autouse réutilisées
    _client_et_stubs,
    _en_tete,
    _en_tete_gestionnaire,
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
