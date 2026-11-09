"""AXE-808 : les rappels partent par l'e-mail ou le SMS du gestionnaire."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.rappels_auto import Regle, rappels_a_creer
from axelcompta.workflow.rappels_envoi import (
    Contexte,
    EnvoisMemoire,
    IntegrationInvalide,
    contenu,
    desinscription_valide,
    envois_du_rappel,
    envoyer_en_attente,
    lien_desinscription,
    preparer_integration,
)

T = TenantId("t")
D = DossierId("d1")
LE = datetime(2026, 11, 9, 10, 0)
CLE = "8HzGpdBIGgfDOSnOFZjfeI0MiLgqAkpdHFEDrKZ0KNI="  # clé Fernet de test


@pytest.fixture(autouse=True)
def _cle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXELCOMPTA_CLE_INTEGRATIONS", CLE)


class _Smtp:
    def __init__(self, panne: bool = False) -> None:
        self.panne = panne
        self.messages: list[tuple[str, str, str]] = []

    def envoyer(self, destinataire: str, sujet: str, texte: str) -> None:
        if self.panne:
            raise ConnectionError("serveur SMTP injoignable")
        self.messages.append((destinataire, sujet, texte))


def _depot() -> EnvoisMemoire:
    depot = EnvoisMemoire()
    smtp = {
        "hote": "smtp.x",
        "port": "587",
        "utilisateur": "u",
        "mot_de_passe": "secret",
        "expediteur": "rappels@serenity.fr",
    }
    depot.brancher(preparer_integration(T, "mail", "smtp", smtp), "admin", LE)
    return depot


def _contexte(email: str | None = "karim@example.com") -> Contexte:
    return Contexte(
        lambda _d, canal: email if canal == "mail" else None, lambda _d: 12, "https://app"
    )


def test_les_identifiants_sont_chiffres_et_les_champs_verifies() -> None:
    integration = _depot().integration(T, "mail")
    assert integration is not None and "secret" not in integration.parametres_chiffres
    with pytest.raises(IntegrationInvalide):
        preparer_integration(T, "mail", "smtp", {"hote": "smtp.x"})
    with pytest.raises(IntegrationInvalide):
        preparer_integration(T, "mail", "http", {})


def test_un_rappel_part_une_fois_sans_montant_avec_le_lien_de_desinscription() -> None:
    depot, smtp = _depot(), _Smtp()
    depot.creer(
        envois_du_rappel("r1", T, D, "Pensez à vos opérations.", ["mail", "appel"], ["mail"], LE)
    )

    premier = envoyer_en_attente(depot, _contexte(), lambda _i: smtp, LE)
    second = envoyer_en_attente(depot, _contexte(), lambda _i: smtp, LE)

    assert premier["envoye"] == 1 and second["envoye"] == 0
    ((destinataire, _sujet, texte),) = smtp.messages
    assert destinataire == "karim@example.com"
    assert "12 opérations vous attendent" in texte and "€" not in texte
    assert "https://app/chauffeur/d1" in texte and "/desinscription?d=d1&c=mail" in texte


def test_un_fournisseur_en_panne_donne_trois_essais_puis_echec() -> None:
    depot, panne = _depot(), _Smtp(panne=True)
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    for _ in range(3):
        envoyer_en_attente(depot, _contexte(), lambda _i: panne, LE)
    (envoi,) = depot.envois.values()
    assert (envoi.statut, envoi.tentatives) == ("echec", 3)
    assert envoi.raison is not None and "injoignable" in envoi.raison


def test_la_desinscription_est_respectee_et_le_lien_signe() -> None:
    depot, smtp = _depot(), _Smtp()
    lien = lien_desinscription("https://app", D, "mail")
    jeton = lien.rsplit("j=", 1)[1]
    assert desinscription_valide("d1", "mail", jeton)
    assert not desinscription_valide("d2", "mail", jeton)
    depot.desinscrire(D, "mail")
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    envoyer_en_attente(depot, _contexte(), lambda _i: smtp, LE)
    (envoi,) = depot.envois.values()
    assert (envoi.statut, envoi.raison, smtp.messages) == ("ignore", "désinscrit", [])


def test_sans_adresse_connue_l_envoi_est_ignore_avec_la_raison() -> None:
    depot = _depot()
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    envoyer_en_attente(depot, _contexte(email=None), lambda _i: _Smtp(), LE)
    (envoi,) = depot.envois.values()
    assert envoi.raison == "e-mail du chauffeur inconnu"


def test_un_sms_tient_en_une_ligne_avec_stop() -> None:
    sujet, texte = contenu("Rappel.", 1, "https://app/x", "https://app/stop", "sms")
    assert sujet == "" and "1 opération vous attend" in texte and "STOP" in texte


def _dossier() -> Dossier:
    return Dossier(
        D, T, "SASU", "IS", "reel_normal", "Karim", "assujetti_taux_reduit", date(2026, 1, 1)
    )


def _regle(declencheur: str, jours: int) -> Regle:
    return Regle("g1", "Message", ("mail",), "tous", (), declencheur, jours, True)


def test_a_traiter_depuis_sept_jours_relance_une_seule_fois() -> None:
    """Critère : une règle « opérations à traiter depuis 7 jours » part une fois."""
    regle, dossier = _regle("a_traiter", 7), _dossier()
    depuis = {D: date(2026, 11, 1)}
    trop_tot = rappels_a_creer([regle], [dossier], {}, depuis, date(2026, 11, 5))
    du = rappels_a_creer([regle], [dossier], {}, depuis, date(2026, 11, 9))
    deja = {("g1", "d1"): [datetime(2026, 11, 9, 8, 0)]}
    encore = rappels_a_creer([regle], [dossier], deja, depuis, date(2026, 11, 10))
    assert (trop_tot, [r.dossier_id for r in du], encore) == ([], [D], [])


def test_avant_cloture_relance_dans_la_fenetre() -> None:
    regle, dossier = _regle("avant_cloture", 15), _dossier()
    assert rappels_a_creer([regle], [dossier], {}, {}, date(2026, 12, 20))
    assert not rappels_a_creer([regle], [dossier], {}, {}, date(2026, 11, 20))
