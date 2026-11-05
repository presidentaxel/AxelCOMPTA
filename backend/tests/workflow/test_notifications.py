from __future__ import annotations

from datetime import date, datetime, timedelta

from axelcompta.categorize.models import Etage
from axelcompta.core.ids import DossierId, EcritureId, UserId
from axelcompta.core.money import Money
from axelcompta.ledger.contrepassation import contrepasser
from axelcompta.ledger.memory import InMemoryLedgerService
from axelcompta.ledger.models import Ecriture, Journal, LigneEcriture, Sens
from axelcompta.workflow.decisions import DecisionHumaine
from axelcompta.workflow.decisions_memory import InMemoryDecisionRepository
from axelcompta.workflow.notifications import (
    INTERVALLE_MIN,
    RAPPEL,
    InMemoryNotificationRepository,
    ecritures_a_trancher,
    message,
    notifier_a_trancher,
    notifier_cloture_a_valider,
)

D = DossierId("d1")
T0 = datetime(2026, 9, 22, 9, 0)


def _ecriture(id_: str, compte: str) -> Ecriture:
    m = Money(1000)
    return Ecriture(
        id=EcritureId(id_),
        dossier_id=D,
        journal=Journal.BQ,
        date=date(2026, 3, 1),
        libelle="secret",
        reference_piece=None,
        lignes=(
            LigneEcriture(compte="512", sens=Sens.CREDIT, montant=m),
            LigneEcriture(compte=compte, sens=Sens.DEBIT, montant=m),
        ),
    )


class Env:
    def __init__(self) -> None:
        self.ledger = InMemoryLedgerService()
        self.decisions = InMemoryDecisionRepository()
        self.notifs = InMemoryNotificationRepository()
        self.ajouter("e1", "471")

    def ajouter(self, id_: str, compte: str) -> None:
        self.ledger.enregistrer(_ecriture(id_, compte))

    def trancher(self, id_: str) -> None:
        self.decisions.enregistrer_decision(
            DecisionHumaine(D, EcritureId(id_), "carburant", Etage.REGLE, 0.9, UserId("u"), T0)
        )

    def notifier(self, maintenant: datetime):  # type: ignore[no-untyped-def]
        return notifier_a_trancher(D, self.ledger, self.decisions, self.notifs, maintenant)


def test_seules_les_ecritures_au_compte_dattente_sans_decision_comptent() -> None:
    env = Env()
    env.ajouter("e2", "6061")
    env.ajouter("e3", "471")
    env.trancher("e3")

    assert ecritures_a_trancher(env.ledger, env.decisions, D) == ("e1",)


def test_rien_a_signaler_ne_notifie_pas() -> None:
    env = Env()
    env.trancher("e1")

    assert env.notifier(T0).statut == "rien_a_faire"
    assert env.notifs.historique == []


def test_premiere_notification_puis_pas_de_doublon_immediat() -> None:
    env = Env()

    assert env.notifier(T0).statut == "creee"
    assert env.notifier(T0 + timedelta(minutes=5)).statut == "deja_notifie"
    assert len(env.notifs.historique) == 1


def test_une_notification_regroupe_tout_ce_qui_attend() -> None:
    env = Env()
    env.ajouter("e2", "471")
    env.ajouter("e3", "471")

    env.notifier(T0)

    (notification,) = env.notifs.historique
    assert notification.message == "3 opérations sont à traiter"
    assert notification.lue_le is None


def test_de_nouvelles_operations_renotifient_apres_lintervalle() -> None:
    env = Env()
    env.notifier(T0)
    env.ajouter("e2", "471")

    assert env.notifier(T0 + INTERVALLE_MIN - timedelta(minutes=1)).statut == "deja_notifie"
    assert env.notifier(T0 + INTERVALLE_MIN).statut == "creee"


def test_sans_nouveaute_un_seul_rappel_par_semaine() -> None:
    env = Env()
    env.notifier(T0)

    assert env.notifier(T0 + RAPPEL - timedelta(hours=1)).statut == "deja_notifie"
    assert env.notifier(T0 + RAPPEL).statut == "creee"
    assert env.notifier(T0 + RAPPEL + timedelta(days=1)).statut == "deja_notifie"


def test_le_message_ne_contient_ni_montant_ni_libelle() -> None:
    env = Env()
    env.notifier(T0)

    (notification,) = env.notifs.historique
    assert "secret" not in notification.message and "10,00" not in notification.message


def test_singulier_et_pluriel() -> None:
    assert message(1) == "Une opération est à traiter"
    assert message(4) == "4 opérations sont à traiter"


def test_marquer_lues_ne_touche_que_les_non_lues_du_dossier() -> None:
    env = Env()
    env.notifier(T0)
    env.ajouter("e2", "471")
    env.notifier(T0 + INTERVALLE_MIN)

    assert env.notifs.marquer_lues(D, T0 + RAPPEL) == 2
    assert env.notifs.marquer_lues(D, T0 + RAPPEL * 2) == 0
    assert env.notifs.marquer_lues(DossierId("autre"), T0) == 0
    assert all(n.lue_le == T0 + RAPPEL for n in env.notifs.historique)


def test_lister_donne_les_plus_recentes_dabord() -> None:
    env = Env()
    env.notifier(T0)
    env.ajouter("e2", "471")
    env.notifier(T0 + INTERVALLE_MIN)

    recentes = env.notifs.lister(D, limite=1)

    assert [n.envoye_le for n in recentes] == [T0 + INTERVALLE_MIN]


def test_une_ecriture_contre_passee_ne_reste_pas_a_trancher() -> None:
    env = Env()
    env.ledger.enregistrer(contrepasser(_ecriture("e1", "471")))

    assert ecritures_a_trancher(env.ledger, env.decisions, D) == ()


def test_la_cloture_a_valider_se_rappelle_chaque_semaine_jusqu_a_la_cloture() -> None:
    notifs = InMemoryNotificationRepository()
    fin = date(2025, 12, 31)
    debut_2026 = datetime(2026, 1, 5, 9, 0)

    assert notifier_cloture_a_valider(D, fin, notifs, datetime(2025, 12, 20)).statut == (
        "rien_a_faire"
    )
    assert notifier_cloture_a_valider(D, fin, notifs, debut_2026).statut == "creee"
    lendemain = debut_2026 + timedelta(days=1)
    assert notifier_cloture_a_valider(D, fin, notifs, lendemain).statut == "deja_notifie"
    assert notifier_cloture_a_valider(D, fin, notifs, debut_2026 + RAPPEL).statut == "creee"
    (premiere, _) = notifs.lister(D, limite=5)[::-1]
    assert premiere.message == "Votre exercice est terminé : relisez-le et validez sa clôture."
