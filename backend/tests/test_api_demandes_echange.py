"""AXE-949 : la demande d'échange de la page publique, sans compte."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from axelcompta.api.routes import get_demandes_echange, get_notifieur_demandes
from axelcompta.prospection.models import DemandeEchange
from axelcompta.prospection.repository import DemandesMemoire
from axelcompta.prospection.service import PLAFOND_PAR_HEURE
from tests.test_demo_api import (  # noqa: F401  (fixtures autouse)
    _client_et_stubs,
    _jwks_factice,
    _ledger_calcule_une_seule_fois,
)

FORMULAIRE = {
    "nom": "Claire Martin",
    "email": "claire@cabinet-martin.fr",
    "organisation": "Cabinet Martin",
    "role": "cabinet",
    "message": "Nous suivons 40 dossiers VTC.",
    "site_web": "",
}


class NotifieurEnregistre:
    def __init__(self, panne: Exception | None = None) -> None:
        self.recues: list[DemandeEchange] = []
        self.panne = panne

    def notifier(self, demande: DemandeEchange) -> None:
        if self.panne is not None:
            raise self.panne
        self.recues.append(demande)


def _client(
    notifieur: NotifieurEnregistre | None,
) -> tuple[TestClient, DemandesMemoire]:
    client = _client_et_stubs()[0]
    depot = DemandesMemoire()
    surcharges = client.app.dependency_overrides  # type: ignore[attr-defined]
    surcharges[get_demandes_echange] = lambda: depot
    surcharges[get_notifieur_demandes] = lambda: notifieur
    return client, depot


def test_une_demande_sans_compte_est_enregistree_et_l_equipe_prevenue() -> None:
    notifieur = NotifieurEnregistre()
    client, depot = _client(notifieur)
    reponse = client.post("/demandes-echange", json=FORMULAIRE)
    assert reponse.status_code == 201, reponse.text
    assert reponse.json() == {"message": "Merci, nous revenons vers vous par e-mail."}
    assert [d.email for d in depot.demandes.values()] == ["claire@cabinet-martin.fr"]
    assert [d.nom for d in notifieur.recues] == ["Claire Martin"]
    assert all(d.notifiee_le is not None for d in depot.demandes.values())


def test_la_demande_est_gardee_meme_si_slack_est_en_panne() -> None:
    client, depot = _client(NotifieurEnregistre(panne=RuntimeError("Slack est tombé")))
    reponse = client.post("/demandes-echange", json=FORMULAIRE)
    assert reponse.status_code == 201, reponse.text
    (demande,) = depot.demandes.values()
    assert demande.notifiee_le is None
    assert demande.tentatives == 1
    assert "Slack est tombé" not in reponse.text


def test_sans_webhook_la_demande_est_gardee_et_le_visiteur_remercie() -> None:
    client, depot = _client(None)
    assert client.post("/demandes-echange", json=FORMULAIRE).status_code == 201
    assert len(depot.demandes) == 1


def test_une_saisie_invalide_repond_422_avec_sa_phrase() -> None:
    client, depot = _client(NotifieurEnregistre())
    reponse = client.post("/demandes-echange", json={**FORMULAIRE, "email": "pas-un-email"})
    assert reponse.status_code == 422
    assert reponse.json() == {"detail": "Indiquez une adresse e-mail valide."}
    assert depot.demandes == {}


def test_un_champ_obligatoire_absent_est_refuse() -> None:
    client, depot = _client(NotifieurEnregistre())
    sans_nom = {cle: valeur for cle, valeur in FORMULAIRE.items() if cle != "nom"}
    assert client.post("/demandes-echange", json=sans_nom).status_code == 422
    assert depot.demandes == {}


def test_un_robot_recoit_la_meme_reponse_et_rien_n_est_garde() -> None:
    notifieur = NotifieurEnregistre()
    client, depot = _client(notifieur)
    reponse = client.post("/demandes-echange", json={**FORMULAIRE, "site_web": "http://spam.fr"})
    assert reponse.status_code == 201
    assert depot.demandes == {}
    assert notifieur.recues == []


def test_un_double_envoi_ne_previent_l_equipe_qu_une_fois() -> None:
    notifieur = NotifieurEnregistre()
    client, depot = _client(notifieur)
    assert client.post("/demandes-echange", json=FORMULAIRE).status_code == 201
    assert client.post("/demandes-echange", json=FORMULAIRE).status_code == 201
    assert len(depot.demandes) == 1
    assert len(notifieur.recues) == 1


def test_au_dela_du_plafond_horaire_la_reponse_est_429() -> None:
    client, depot = _client(NotifieurEnregistre())
    maintenant = datetime.now(UTC)
    for rang in range(PLAFOND_PAR_HEURE):
        demande = DemandeEchange(
            id=f"d{rang}",
            nom="X",
            email=f"x{rang}@exemple.fr",
            organisation="Y",
            role="cabinet",
            message=None,
            cree_le=maintenant,
        )
        depot.ajouter(demande)
    reponse = client.post("/demandes-echange", json=FORMULAIRE)
    assert reponse.status_code == 429
    assert "Réessayez" in reponse.json()["detail"]
    assert len(depot.demandes) == PLAFOND_PAR_HEURE


def test_un_corps_demesure_est_refuse_avant_tout_traitement() -> None:
    client, depot = _client(NotifieurEnregistre())
    reponse = client.post("/demandes-echange", json={**FORMULAIRE, "message": "x" * 20000})
    assert reponse.status_code == 422
    assert depot.demandes == {}
