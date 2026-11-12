"""AXE-808 : les rappels partent par l'e-mail ou le SMS du gestionnaire ;
AXE-872 : par le branchement du dossier, sinon par celui par défaut."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.tenants.branchements import Branchement, BranchementsMemoire, nouveau
from axelcompta.tenants.models import Dossier
from axelcompta.workflow.rappels_auto import Regle, rappels_a_creer
from axelcompta.workflow.rappels_envoi import (
    Contexte,
    EnvoisMemoire,
    contenu,
    desinscription_valide,
    envois_du_rappel,
    envoyer_en_attente,
    lien_desinscription,
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


SMTP = {
    "hote": "smtp.x",
    "port": "587",
    "utilisateur": "u",
    "mot_de_passe": "secret",
    "expediteur": "rappels@serenity.fr",
}


def _smtp(branchements: BranchementsMemoire, nom: str) -> Branchement:
    cree = nouveau(branchements.lister(T), T, "mail", "smtp", nom, SMTP)
    branchements.enregistrer([cree], "admin", LE)
    return cree


def _depots() -> tuple[EnvoisMemoire, BranchementsMemoire]:
    branchements = BranchementsMemoire()
    _smtp(branchements, "SMTP principal")
    return EnvoisMemoire(), branchements


def _contexte(email: str | None = "karim@example.com") -> Contexte:
    return Contexte(
        lambda _d, canal: email if canal == "mail" else None, lambda _d: 12, "https://app"
    )


def test_un_rappel_part_une_fois_sans_montant_avec_le_lien_de_desinscription() -> None:
    (depot, branchements), smtp = _depots(), _Smtp()
    depot.creer(
        envois_du_rappel("r1", T, D, "Pensez à vos opérations.", ["mail", "appel"], ["mail"], LE)
    )

    premier = envoyer_en_attente(depot, branchements, _contexte(), lambda _b: smtp, LE)
    second = envoyer_en_attente(depot, branchements, _contexte(), lambda _b: smtp, LE)

    assert premier["envoye"] == 1 and second["envoye"] == 0
    ((destinataire, _sujet, texte),) = smtp.messages
    assert destinataire == "karim@example.com"
    assert "12 opérations vous attendent" in texte and "€" not in texte
    assert "https://app/chauffeur/d1" in texte and "/desinscription?d=d1&c=mail" in texte


def test_un_fournisseur_en_panne_donne_trois_essais_puis_echec() -> None:
    (depot, branchements), panne = _depots(), _Smtp(panne=True)
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    for _ in range(3):
        envoyer_en_attente(depot, branchements, _contexte(), lambda _b: panne, LE)
    (envoi,) = depot.envois.values()
    assert (envoi.statut, envoi.tentatives) == ("echec", 3)
    assert envoi.raison is not None and "injoignable" in envoi.raison


def test_la_desinscription_est_respectee_et_le_lien_signe() -> None:
    (depot, branchements), smtp = _depots(), _Smtp()
    lien = lien_desinscription("https://app", D, "mail")
    jeton = lien.rsplit("j=", 1)[1]
    assert desinscription_valide("d1", "mail", jeton)
    assert not desinscription_valide("d2", "mail", jeton)
    depot.desinscrire(D, "mail")
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    envoyer_en_attente(depot, branchements, _contexte(), lambda _b: smtp, LE)
    (envoi,) = depot.envois.values()
    assert (envoi.statut, envoi.raison, smtp.messages) == ("ignore", "désinscrit", [])


def test_sans_adresse_connue_l_envoi_est_ignore_avec_la_raison() -> None:
    depot, branchements = _depots()
    depot.creer(envois_du_rappel("r1", T, D, "Message", ["mail"], ["mail"], LE))
    envoyer_en_attente(depot, branchements, _contexte(email=None), lambda _b: _Smtp(), LE)
    (envoi,) = depot.envois.values()
    assert envoi.raison == "e-mail du chauffeur inconnu"


def test_le_dossier_part_par_son_smtp_et_les_autres_par_celui_par_defaut() -> None:
    """Critère AXE-872 : les rappels partent par le branchement du dossier,
    sinon par celui par défaut ; l'envoi garde lequel."""
    depot, branchements = _depots()
    nord = _smtp(branchements, "SMTP agence Nord")
    branchements.choisir_pour_dossier(T, D, "mail", nord.id)
    autre = DossierId("d2")
    depot.creer(envois_du_rappel("r1", T, D, "M", ["mail"], ["mail"], LE))
    depot.creer(envois_du_rappel("r2", T, autre, "M", ["mail"], ["mail"], LE))
    utilises: list[str] = []

    def expediteur(branchement: Branchement) -> _Smtp:
        utilises.append(branchement.nom)
        return _Smtp()

    envoyer_en_attente(depot, branchements, _contexte(), expediteur, LE)

    assert sorted(utilises) == ["SMTP agence Nord", "SMTP principal"]
    assert depot.envois["r1:mail"].branchement_id == nord.id
    assert depot.envois["r2:mail"].branchement_id != nord.id


def test_un_choix_desactive_revient_au_branchement_par_defaut() -> None:
    depot, branchements = _depots()
    nord = _smtp(branchements, "SMTP agence Nord")
    branchements.choisir_pour_dossier(T, D, "mail", nord.id)
    branchements.enregistrer([replace(nord, actif=False)], "admin", LE)
    depot.creer(envois_du_rappel("r1", T, D, "M", ["mail"], ["mail"], LE))
    utilises: list[str] = []

    def expediteur(branchement: Branchement) -> _Smtp:
        utilises.append(branchement.nom)
        return _Smtp()

    envoyer_en_attente(depot, branchements, _contexte(), expediteur, LE)
    assert utilises == ["SMTP principal"]


def test_sans_aucun_branchement_l_envoi_est_ignore() -> None:
    depot = EnvoisMemoire()
    depot.creer(envois_du_rappel("r1", T, D, "M", ["mail"], ["mail"], LE))
    envoyer_en_attente(depot, BranchementsMemoire(), _contexte(), lambda _b: _Smtp(), LE)
    assert depot.envois["r1:mail"].raison == "intégration retirée"


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
