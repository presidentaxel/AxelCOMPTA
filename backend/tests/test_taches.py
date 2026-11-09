"""Enchaînement des tâches planifiées : synchro puis notifications, par
portefeuille, sans qu'une étape en échec n'empêche l'autre."""

from __future__ import annotations

from datetime import date

import pytest

from axelcompta.core.ids import DossierId, TenantId
from axelcompta.core.metriques import METRIQUES
from axelcompta.ledger.balance import SoldeJournal
from axelcompta.synchro_digifactory import ResultatDossier
from axelcompta.taches import BilanTaches, controler_balance, lancer_taches
from axelcompta.tenants.memory import InMemoryDossierRepository
from axelcompta.tenants.models import Dossier, Tenant
from axelcompta.tenants.tags import EXCLUSIONS_PAR_DEFAUT, TAG_SOCIETE_DU_GESTIONNAIRE, EtatTags
from axelcompta.workflow.notifications import ResultatNotification


def _depot(*dossiers: tuple[str, str, str | None]) -> InMemoryDossierRepository:
    depot = InMemoryDossierRepository()
    for id_, tenant, contact in dossiers:
        depot.enregistrer_tenant(Tenant(id=TenantId(tenant), nom=tenant))
        depot.enregistrer(
            Dossier(
                id=DossierId(id_),
                tenant_id=TenantId(tenant),
                forme_juridique="SASU",
                regime_imposition="IS",
                regime_tva="franchise",
                nom=id_,
                tva_recettes_regime="franchise",
                exercice_debut=date(2026, 1, 1),
                contact_nr=contact,
            )
        )
    return depot


def _notifier_tout(dossiers: tuple[Dossier, ...]) -> list[ResultatNotification]:
    return [ResultatNotification(d.id, "creee", 1) for d in dossiers]


class _Appels:
    def __init__(self) -> None:
        self.synchro: list[tuple[str, ...]] = []

    def synchroniser(
        self, dossiers: tuple[Dossier, ...], sans_classement: frozenset[DossierId]
    ) -> list[ResultatDossier]:
        self.synchro.append(tuple(d.id for d in dossiers))
        self.sans_classement = sans_classement
        return [ResultatDossier(d.id) for d in dossiers]


def test_un_portefeuille_sans_contact_digifactory_nest_pas_synchronise() -> None:
    appels = _Appels()
    depot = _depot(("a1", "A", None), ("b1", "B", "12"), ("b2", "B", None))

    bilan = lancer_taches(depot, appels.synchroniser, _notifier_tout)

    assert appels.synchro == [("b1", "b2")]
    assert bilan.lignes == [
        "A notifications : 1 créées, 0 en échec",
        "B synchro : 2 ok, 0 en échec",
        "B notifications : 2 créées, 0 en échec",
    ]
    assert not bilan.echec


def test_une_synchro_qui_plante_nempeche_pas_les_notifications() -> None:
    def planter(
        dossiers: tuple[Dossier, ...], sans_classement: frozenset[DossierId]
    ) -> list[ResultatDossier]:
        raise ConnectionError("digifactory")

    bilan = lancer_taches(_depot(("b1", "B", "12")), planter, _notifier_tout)

    assert bilan.echec
    assert bilan.lignes[-1] == "B notifications : 1 créées, 0 en échec"


@pytest.mark.parametrize(
    ("resultat_synchro", "statut_notif"),
    [
        (ResultatDossier(DossierId("b1"), erreur="401"), "creee"),
        (ResultatDossier(DossierId("b1")), "echec"),
    ],
)
def test_un_dossier_en_echec_rend_le_passage_en_echec(
    resultat_synchro: ResultatDossier, statut_notif: str
) -> None:
    bilan = lancer_taches(
        _depot(("b1", "B", "12")),
        lambda _d, _s: [resultat_synchro],
        lambda d: [ResultatNotification(x.id, statut_notif) for x in d],
    )

    assert bilan.echec


def test_sans_synchro_seules_les_notifications_passent() -> None:
    bilan = lancer_taches(_depot(("b1", "B", "12")), None, _notifier_tout)

    assert bilan.lignes == ["B notifications : 1 créées, 0 en échec"]


def test_les_bascules_de_regime_passent_avant_les_notifications() -> None:
    appels: list[str] = []

    def bascules(dossiers: tuple[Dossier, ...]) -> int:
        appels.append("bascules")
        return 1

    def notifier(dossiers: tuple[Dossier, ...]) -> list[ResultatNotification]:
        appels.append("notifications")
        return _notifier_tout(dossiers)

    bilan = lancer_taches(_depot(("a1", "A", None)), None, notifier, bascules)

    assert appels == ["bascules", "notifications"]
    assert "A bascules de régime : 1 enregistrées" in bilan.lignes


def test_une_bascule_en_echec_n_empeche_pas_les_notifications() -> None:
    def planter(dossiers: tuple[Dossier, ...]) -> int:
        raise ConnectionError("base")

    bilan = lancer_taches(_depot(("a1", "A", None)), None, _notifier_tout, planter)

    assert bilan.echec
    assert bilan.lignes[-1] == "A notifications : 1 créées, 0 en échec"


def test_les_tags_excluent_de_la_synchro_du_classement_et_des_rappels() -> None:
    """AXE-829 : `b1` est une société du gestionnaire (exclue de tout), `b2`
    un chauffeur qu'on ne veut pas classer automatiquement."""
    appels = _Appels()
    notifies: list[str] = []
    depot = _depot(("b1", "B", "12"), ("b2", "B", "13"), ("b3", "B", "14"))
    exclusions = dict(EXCLUSIONS_PAR_DEFAUT, categorisation=frozenset({"sans_auto"}))
    etat = EtatTags(
        {
            DossierId("b1"): frozenset({TAG_SOCIETE_DU_GESTIONNAIRE}),
            DossierId("b2"): frozenset({"sans_auto"}),
        },
        exclusions,
    )

    def notifier(dossiers: tuple[Dossier, ...]) -> list[ResultatNotification]:
        notifies.extend(d.id for d in dossiers)
        return _notifier_tout(dossiers)

    lancer_taches(depot, appels.synchroniser, notifier, perimetre=lambda _t: etat)

    assert appels.synchro == [("b2", "b3")]
    assert appels.sans_classement == frozenset({"b2"})
    assert notifies == ["b2", "b3"]


def test_les_caches_sont_prechauffes_avant_les_notifications() -> None:
    """AXE-824 : après la synchro, le premier affichage lit des valeurs gardées."""
    appels: list[str] = []

    def prechauffer(dossiers: tuple[Dossier, ...]) -> int:
        appels.append("caches")
        return len(dossiers)

    def notifier(dossiers: tuple[Dossier, ...]) -> list[ResultatNotification]:
        appels.append("notifications")
        return _notifier_tout(dossiers)

    bilan = lancer_taches(_depot(("a1", "A", None)), None, notifier, prechauffer=prechauffer)

    assert appels == ["caches", "notifications"]
    assert "A caches : 1 dossiers recalculés" in bilan.lignes


def test_un_echec_de_prechauffage_ne_bloque_rien() -> None:
    def planter(dossiers: tuple[Dossier, ...]) -> int:
        raise ConnectionError("base")

    bilan = lancer_taches(_depot(("a1", "A", None)), None, _notifier_tout, prechauffer=planter)

    assert not bilan.echec
    assert bilan.lignes[-1] == "A notifications : 1 créées, 0 en échec"


def test_la_balance_equilibree_est_notee_sans_alerte() -> None:
    alertes: list[str] = []
    bilan = BilanTaches()
    controler_balance(bilan, lambda: [SoldeJournal(DossierId("a"), "BQ", 5, 5)], alertes.append)
    assert bilan.lignes == ["balance : équilibrée"]
    assert not bilan.echec and alertes == []


def test_un_desequilibre_de_balance_declenche_l_alerte() -> None:
    """AXE-807, I7 : alerte, ligne au journal, échec du passage ; rien n'est
    corrigé."""
    alertes: list[str] = []
    bilan = BilanTaches()
    controler_balance(bilan, lambda: [SoldeJournal(DossierId("a"), "OD", 12, 10)], alertes.append)
    assert bilan.echec
    assert len(alertes) == 2  # le journal, puis le total du dossier
    assert bilan.lignes[0].startswith("ALERTE balance déséquilibrée : a, journal OD")
    assert "balance_desequilibree_total 2" in METRIQUES.texte()
