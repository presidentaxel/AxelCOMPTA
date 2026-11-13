"""AXE-849 : relecture hebdomadaire des registres, écarts posés sur le
dossier, et ce que voient le dirigeant et le gestionnaire."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from axelcompta.api.routes import _sujets_ecarts, get_dossiers, get_registres
from axelcompta.core.ids import DossierId, TenantId
from axelcompta.registres_officiels import (
    Insee,
    Rne,
    lecteur_depuis_env,
    relire_dossier,
    relire_portefeuilles,
)
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.registres import FicheOfficielle, fiche_rne
from axelcompta.tenants.registres_depot import RegistresMemoire
from tests.tenants.registres_fixtures import RNE_SAS_PLURIPERSONNELLE, SIREN
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client,
    _en_tete,
    _en_tete_gestionnaire,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

KARIM = "DEMO_karim"
MAINTENANT = datetime(2026, 11, 10, 3, 0, tzinfo=UTC)


def _fiche_sas(siren: str = SIREN) -> FicheOfficielle | None:
    return (
        fiche_rne(RNE_SAS_PLURIPERSONNELLE, SIREN, date(2026, 11, 10)) if siren == SIREN else None
    )


def _maj(
    depot: InMemoryDossierRepository,
) -> Callable[[DossierId, Callable[[Dossier], Dossier]], None]:
    def maj(dossier_id: DossierId, changer: Callable[[Dossier], Dossier]) -> None:
        dossier = depot.obtenir(dossier_id)
        assert dossier is not None
        depot.reconfigurer_depuis_sirene(changer(dossier))

    return maj


def _portefeuille() -> tuple[InMemoryDossierRepository, RegistresMemoire]:
    depot = InMemoryDossierRepository()
    depot.enregistrer_tenant(Tenant(id=TenantId("T"), nom="T"))
    for numero, siren in (("1", SIREN), ("2", None), ("3", "111111111")):
        depot.enregistrer(
            Dossier(
                id=DossierId(f"DIGI_{numero}"),
                tenant_id=TenantId("T"),
                forme_juridique="SASU",
                regime_imposition="IS",
                regime_tva="reel_normal",
                nom=numero,
                tva_recettes_regime="assujetti_taux_reduit",
                exercice_debut=date(2026, 1, 1),
                siren=siren,
            )
        )
    return depot, RegistresMemoire(_maj(depot))


def test_seuls_les_dossiers_avec_siren_sont_relus_et_l_ecart_est_pose() -> None:
    depot, registres = _portefeuille()
    relus, erreurs = relire_portefeuilles(depot, registres, _fiche_sas, MAINTENANT)
    assert (relus, erreurs) == (1, [])
    dossier = depot.obtenir(DossierId("DIGI_1"))
    assert dossier is not None
    assert [(e.champ, e.declare, e.officiel) for e in dossier.ecarts_registre] == [
        ("forme_juridique", "SASU", "SAS")
    ]


def test_un_dossier_n_est_relu_qu_une_fois_par_semaine() -> None:
    depot, registres = _portefeuille()
    relire_portefeuilles(depot, registres, _fiche_sas, MAINTENANT)
    dossier_id, fiche, _ = registres.lectures[0]
    registres.lectures[0] = (dossier_id, fiche, MAINTENANT)  # lu à cet instant
    six_jours = MAINTENANT + timedelta(days=6)
    assert relire_portefeuilles(depot, registres, _fiche_sas, six_jours) == (0, [])
    sept_jours = MAINTENANT + timedelta(days=7)
    assert relire_portefeuilles(depot, registres, _fiche_sas, sept_jours)[0] == 1


def test_une_erreur_de_registre_n_arrete_pas_les_autres() -> None:
    depot, registres = _portefeuille()

    def lire(siren: str) -> FicheOfficielle | None:
        if siren == "111111111":
            raise TimeoutError("RNE lent")
        return _fiche_sas(siren)

    relus, erreurs = relire_portefeuilles(depot, registres, lire, MAINTENANT)
    assert relus == 1
    assert erreurs == ["DIGI_3 : TimeoutError: RNE lent"]


def test_un_rne_refuse_laisse_la_fiche_insee(monkeypatch: pytest.MonkeyPatch) -> None:
    fiche = _fiche_sas()
    assert fiche is not None

    def insee(self: Insee, siren: str, jour: date) -> FicheOfficielle:
        return fiche

    def rne(self: Rne, siren: str, jour: date) -> FicheOfficielle:
        requete = httpx.Request(
            "POST", "https://registre-national-entreprises.inpi.fr/api/sso/login"
        )
        reponse = httpx.Response(403, request=requete)
        raise httpx.HTTPStatusError("403", request=requete, response=reponse)

    monkeypatch.setattr(Insee, "lire", insee)
    monkeypatch.setattr(Rne, "lire", rne)
    lire = lecteur_depuis_env(
        {"INSEE_API_KEY": "k", "INPI_RNE_USERNAME": "u", "INPI_RNE_PASSWORD": "p"}
    )
    assert lire is not None
    assert lire(SIREN) == fiche


def test_sans_cle_rien_n_est_lu() -> None:
    assert lecteur_depuis_env({}) is None
    assert lecteur_depuis_env({"INPI_RNE_USERNAME": "u"}) is None
    assert lecteur_depuis_env({"INSEE_API_KEY": "k"}) is not None


def _client_avec_ecart() -> tuple[TestClient, RegistresMemoire]:
    """Karim, déclaré SASU, que le RNE dit SAS (critère du ticket)."""
    client = _client()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    dossier = depot.obtenir(DossierId(KARIM))
    depot.reconfigurer_depuis_sirene(
        dataclasses.replace(dossier, siren=SIREN, forme_juridique="SASU")
    )
    registres = RegistresMemoire(_maj(depot))
    client.app.dependency_overrides[get_registres] = lambda: registres  # type: ignore[attr-defined]
    fiche = _fiche_sas()
    assert fiche is not None
    relire_dossier(registres, depot.obtenir(DossierId(KARIM)), lambda _s: fiche)
    return client, registres


def test_critere_le_gestionnaire_voit_l_ecart_et_la_liasse_est_refusee() -> None:
    client, _ = _client_avec_ecart()
    liste = client.get("/dossiers", headers=_en_tete_gestionnaire()).json()
    karim = next(d for d in liste if d["dossier_id"] == KARIM)
    assert karim["ecarts_registre"] == ["Forme déclarée SASU, forme au registre SAS."]
    liasse = client.get(f"/dossiers/{KARIM}/liasse-fiscale.pdf", headers=_en_tete(KARIM))
    assert liasse.status_code == 409
    assert "forme au registre SAS" in liasse.json()["detail"]


def test_un_ecart_est_un_sujet_de_la_file_expert() -> None:
    client, _ = _client_avec_ecart()
    depot = client.app.dependency_overrides[get_dossiers]()  # type: ignore[attr-defined]
    dossier = depot.obtenir(DossierId(KARIM))
    sujets = _sujets_ecarts(dossier)
    assert [(s.nature, s.imputable, s.detail, s.montant_cts, s.ecriture_id) for s in sujets] == [
        ("registre", False, "Forme déclarée SASU, forme au registre SAS.", None, None)
    ]


def test_un_dossier_sans_ecart_n_affiche_rien_de_plus() -> None:
    liste = _client().get("/dossiers", headers=_en_tete_gestionnaire()).json()
    assert all(d["ecarts_registre"] == [] for d in liste)


def test_le_dirigeant_retient_la_forme_du_registre_et_c_est_trace() -> None:
    client, registres = _client_avec_ecart()
    vue = client.get(f"/dossiers/{KARIM}/registre", headers=_en_tete(KARIM)).json()
    assert (vue["forme_juridique"], vue["capital_cts"]) == ("SAS", 100000)
    assert vue["ecarts"][0]["phrase"] == "Forme déclarée SASU, forme au registre SAS."
    reponse = client.post(
        f"/dossiers/{KARIM}/registre/ecarts/forme_juridique",
        json={"retenue": "officielle"},
        headers=_en_tete(KARIM),
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["forme_juridique"] == "SAS"
    assert [(r.ecart.champ, r.retenue) for r in registres.resolutions] == [
        ("forme_juridique", "officielle")
    ]
    apres = client.get(f"/dossiers/{KARIM}/registre", headers=_en_tete(KARIM)).json()
    assert apres["ecarts"] == []


def test_un_autre_chauffeur_ne_tranche_pas_et_un_champ_inconnu_est_404() -> None:
    client, _ = _client_avec_ecart()
    autre = client.post(
        f"/dossiers/{KARIM}/registre/ecarts/forme_juridique",
        json={"retenue": "declaree"},
        headers=_en_tete("DEMO_sophie"),
    )
    assert autre.status_code in (403, 404)
    inconnu = client.post(
        f"/dossiers/{KARIM}/registre/ecarts/capital",
        json={"retenue": "declaree"},
        headers=_en_tete(KARIM),
    )
    assert inconnu.status_code == 404
