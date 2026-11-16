"""AXE-949 : recevoir une demande, prévenir l'équipe, réessayer sans rien perdre."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from axelcompta.core.errors import SaisieInvalide
from axelcompta.prospection.models import DemandeEchange, TropDeDemandes
from axelcompta.prospection.repository import DemandesMemoire
from axelcompta.prospection.service import (
    PLAFOND_PAR_HEURE,
    TENTATIVES_MAX,
    notifier,
    recevoir,
    relancer,
)

MAINTENANT = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)


class NotifieurEnregistre:
    def __init__(self, panne: Exception | None = None) -> None:
        self.recues: list[DemandeEchange] = []
        self.panne = panne

    def notifier(self, demande: DemandeEchange) -> None:
        if self.panne is not None:
            raise self.panne
        self.recues.append(demande)


def _recevoir(
    depot: DemandesMemoire,
    *,
    id: str = "d1",  # noqa: A002
    email: str = "claire@cabinet.fr",
    piege: str = "",
    maintenant: datetime = MAINTENANT,
) -> DemandeEchange | None:
    return recevoir(
        depot,
        id=id,
        nom="Claire",
        email=email,
        organisation="Cabinet",
        role="cabinet",
        message=None,
        piege=piege,
        maintenant=maintenant,
    )


def _demande_recue(depot: DemandesMemoire) -> DemandeEchange:
    demande = _recevoir(depot)
    assert demande is not None
    return demande


def test_une_demande_valide_est_enregistree_et_rendue() -> None:
    depot = DemandesMemoire()
    demande = _demande_recue(depot)
    assert depot.demandes["d1"] == demande


def test_une_saisie_invalide_n_enregistre_rien() -> None:
    depot = DemandesMemoire()
    with pytest.raises(SaisieInvalide):
        recevoir(
            depot,
            id="d1",
            nom="",
            email="claire@cabinet.fr",
            organisation="Cabinet",
            role="cabinet",
            message=None,
            piege="",
            maintenant=MAINTENANT,
        )
    assert depot.demandes == {}


def test_un_champ_piege_rempli_ne_garde_rien() -> None:
    depot = DemandesMemoire()
    assert _recevoir(depot, piege="http://spam.example") is None
    assert depot.demandes == {}


def test_la_meme_adresse_dans_le_quart_d_heure_n_ajoute_rien() -> None:
    depot = DemandesMemoire()
    assert _recevoir(depot) is not None
    assert _recevoir(depot, id="d2", maintenant=MAINTENANT + timedelta(minutes=5)) is None
    assert list(depot.demandes) == ["d1"]


def test_la_meme_adresse_plus_tard_est_une_nouvelle_demande() -> None:
    depot = DemandesMemoire()
    _recevoir(depot)
    assert _recevoir(depot, id="d2", maintenant=MAINTENANT + timedelta(minutes=16)) is not None


def test_au_dela_du_plafond_horaire_on_demande_de_patienter() -> None:
    depot = DemandesMemoire()
    for rang in range(PLAFOND_PAR_HEURE):
        assert _recevoir(depot, id=f"d{rang}", email=f"p{rang}@exemple.fr") is not None
    with pytest.raises(TropDeDemandes, match="Réessayez"):
        _recevoir(depot, id="trop", email="autre@exemple.fr")
    assert "trop" not in depot.demandes


def test_le_plafond_se_libere_apres_une_heure() -> None:
    depot = DemandesMemoire()
    for rang in range(PLAFOND_PAR_HEURE):
        _recevoir(depot, id=f"d{rang}", email=f"p{rang}@exemple.fr")
    plus_tard = MAINTENANT + timedelta(hours=1, minutes=1)
    assert _recevoir(depot, id="suite", email="autre@exemple.fr", maintenant=plus_tard) is not None


def test_notifier_previent_l_equipe_et_marque_la_demande() -> None:
    depot = DemandesMemoire()
    demande = _demande_recue(depot)
    notifieur = NotifieurEnregistre()
    assert notifier(depot, notifieur, demande, MAINTENANT) is True
    assert notifieur.recues == [demande]
    assert depot.demandes["d1"].notifiee_le == MAINTENANT


def test_sans_webhook_la_demande_attend_sans_compter_d_essai() -> None:
    depot = DemandesMemoire()
    demande = _demande_recue(depot)
    assert notifier(depot, None, demande, MAINTENANT) is False
    assert depot.demandes["d1"].tentatives == 0
    assert depot.demandes["d1"].notifiee_le is None


def test_un_echec_est_note_sans_l_adresse_du_webhook() -> None:
    depot = DemandesMemoire()
    demande = _demande_recue(depot)
    secret = "https://hooks.slack.com/services/T/B/secret"
    requete = httpx.Request("POST", secret)
    panne = httpx.HTTPStatusError(
        f"404 pour {secret}", request=requete, response=httpx.Response(404, request=requete)
    )
    assert notifier(depot, NotifieurEnregistre(panne), demande, MAINTENANT) is False
    gardee = depot.demandes["d1"]
    assert gardee.tentatives == 1
    assert gardee.derniere_erreur == "Slack a répondu 404"


def test_une_autre_panne_garde_son_type() -> None:
    depot = DemandesMemoire()
    demande = _demande_recue(depot)
    notifier(depot, NotifieurEnregistre(httpx.ConnectTimeout("délai")), demande, MAINTENANT)
    assert depot.demandes["d1"].derniere_erreur == "ConnectTimeout"


def test_relancer_reprend_les_demandes_non_notifiees() -> None:
    depot = DemandesMemoire()
    _recevoir(depot)
    notifieur = NotifieurEnregistre()
    ligne = relancer(depot, notifieur, MAINTENANT + timedelta(minutes=10))
    assert ligne == "demandes d'échange : 1 notifiée(s) sur 1"
    assert depot.demandes["d1"].notifiee_le is not None
    suite = relancer(depot, notifieur, MAINTENANT + timedelta(hours=1))
    assert suite == "demandes d'échange : rien en attente"


def test_relancer_laisse_le_temps_a_la_premiere_notification() -> None:
    depot = DemandesMemoire()
    _recevoir(depot)
    ligne = relancer(depot, NotifieurEnregistre(), MAINTENANT + timedelta(minutes=1))
    assert ligne == "demandes d'échange : rien en attente"


def test_relancer_sans_webhook_le_dit_sans_rien_changer() -> None:
    depot = DemandesMemoire()
    _recevoir(depot)
    ligne = relancer(depot, None, MAINTENANT + timedelta(minutes=10))
    assert ligne == "demandes d'échange : 1 en attente, aucun webhook Slack"
    assert depot.demandes["d1"].tentatives == 0


def test_apres_les_essais_permis_la_demande_n_est_plus_relancee_et_sentry_est_prevenu(
    caplog: pytest.LogCaptureFixture,
) -> None:
    depot = DemandesMemoire()
    _recevoir(depot)
    panne = NotifieurEnregistre(httpx.ConnectTimeout("délai"))
    with caplog.at_level(logging.ERROR, logger="axelcompta.prospection.service"):
        for passage in range(TENTATIVES_MAX + 2):
            relancer(depot, panne, MAINTENANT + timedelta(hours=passage + 1))
    assert depot.demandes["d1"].tentatives == TENTATIVES_MAX
    erreurs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(erreurs) == 1
    assert "d1" in erreurs[0].getMessage()
    assert "claire@cabinet.fr" not in erreurs[0].getMessage()
