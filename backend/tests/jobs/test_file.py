from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from axelcompta.jobs.executer import executer
from axelcompta.jobs.file import (
    TYPE_RAPPROCHEMENT_ROLLEE,
    TYPE_SYNCHRO,
    FileMemoire,
    Job,
    TypeInconnu,
    deja_couvert,
)
from axelcompta.jobs.postgres import REQUETE_PRENDRE
from axelcompta.tenants.roles import peut
from axelcompta.workflow.audit import ACTE_CONNEXION, ACTE_CONSULTATION, ACTE_EXPORT


def test_la_priorite_basse_passe_devant() -> None:
    file = FileMemoire()
    file.deposer("bas", "ten", "notifier", "{}", priorite=10)
    file.deposer("haut", "ten", "synchro_digifactory", "{}", priorite=0)
    assert file.prendre("w1") is not None
    assert file.lire("haut").statut == "en_cours"
    assert file.lire("bas").statut == "en_attente"


def test_deux_workers_ne_prennent_pas_le_meme_job() -> None:
    file = FileMemoire()
    file.deposer("seul", "ten", "ml", "{}")
    assert file.prendre("w1") is not None
    assert file.prendre("w2") is None


def test_un_echec_isole_repart_en_attente_sans_clore() -> None:
    file = FileMemoire()
    file.deposer("j", "ten", "notifier", "{}")
    assert file.prendre("w") is not None
    assert file.echouer("j") is False
    assert file.lire("j").statut == "en_attente"


def test_trois_echecs_sortent_le_job_de_la_file() -> None:
    file = FileMemoire()
    file.deposer("j", "ten", "notifier", "{}")

    def casse(job: object) -> None:
        raise RuntimeError(job)

    for _ in range(3):
        executer(file, "w", {"notifier": casse})
    assert file.lire("j").statut == "echec"
    assert file.prendre("w") is None


def test_un_handler_termine_le_job() -> None:
    file = FileMemoire()
    file.deposer("j", "ten", "ml", "{}")
    vus: list[str] = []
    executer(file, "w", {"ml": lambda job: vus.append(job.type)})
    assert vus == ["ml"]
    assert file.lire("j").statut == "fait"


def test_un_type_inconnu_est_refuse() -> None:
    with pytest.raises(TypeInconnu):
        FileMemoire().deposer("j", "ten", "autre", "{}")


def test_la_requete_postgres_saute_les_lignes_verrouillees() -> None:
    assert "FOR UPDATE SKIP LOCKED" in REQUETE_PRENDRE


def test_les_roles_v1() -> None:
    assert peut("lecture", "lire")
    assert not peut("lecture", "ecrire")
    assert peut("membre", "ecrire")
    assert not peut("membre", "administrer")
    assert peut("admin", "administrer")
    assert not peut("inconnu", "lire")


def test_les_actes_dacces_ont_un_nom() -> None:
    assert {ACTE_CONNEXION, ACTE_EXPORT, ACTE_CONSULTATION} == {
        "connexion",
        "export",
        "consultation",
    }


def test_deux_demandes_identiques_en_attente_n_en_font_qu_une() -> None:
    file = FileMemoire()
    assert file.demander("t", TYPE_SYNCHRO).id == file.demander("t", TYPE_SYNCHRO).id


def test_une_demande_pendant_un_job_en_cours_attend_son_tour() -> None:
    """AXE-921 : SEVEN CAR PRESTIGE ajouté pendant une synchro en cours.
    Le job en cours a déjà lu les décisions : une seconde synchro doit suivre."""
    file = FileMemoire()
    premiere = file.demander("t", TYPE_SYNCHRO)
    en_cours = file.prendre("w")
    assert en_cours is not None and en_cours.id == premiere.id
    seconde = file.demander("t", TYPE_SYNCHRO)
    assert seconde.id != premiere.id and seconde.statut == "en_attente"
    file.terminer(premiere.id)
    suivant = file.prendre("w")
    assert suivant is not None and suivant.id == seconde.id


def test_deux_dossiers_differents_ont_chacun_leur_job() -> None:
    """Le payload porte le dossier : la demande de l'un n'absorbe pas l'autre."""
    file = FileMemoire()
    a = file.demander("t", TYPE_RAPPROCHEMENT_ROLLEE, '{"dossier_id": "A"}')
    b = file.demander("t", TYPE_RAPPROCHEMENT_ROLLEE, '{"dossier_id": "B"}')
    assert a.id != b.id


def test_un_job_en_echec_ne_double_pas_une_demande_qui_attend() -> None:
    file = FileMemoire()
    premiere = file.demander("t", TYPE_SYNCHRO)
    file.prendre("w")
    seconde = file.demander("t", TYPE_SYNCHRO)
    assert file.echouer(premiere.id) is True
    assert (file.lire(premiere.id).statut, file.lire(seconde.id).statut) == ("echec", "en_attente")


MIDI = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def test_un_job_abandonne_par_son_worker_revient_en_attente() -> None:
    """AXE-958 : le worker tué au redéploiement laissait le job en cours."""
    file = FileMemoire()
    file.deposer("j", "ten", TYPE_SYNCHRO, "{}")
    file.prendre("worker", MIDI)
    assert file.relacher_abandonnes(MIDI + timedelta(hours=3)) == ["j"]
    assert file.lire("j").statut == "en_attente"
    assert file.prendre("worker", MIDI) is not None


def test_un_job_en_cours_depuis_peu_n_est_pas_touche() -> None:
    file = FileMemoire()
    file.deposer("j", "ten", TYPE_SYNCHRO, "{}")
    file.prendre("worker", MIDI)
    assert file.relacher_abandonnes(MIDI + timedelta(minutes=30)) == []
    assert file.lire("j").statut == "en_cours"


def test_un_job_abandonne_sans_essai_restant_passe_en_echec() -> None:
    file = FileMemoire()
    file.deposer("j", "ten", TYPE_SYNCHRO, "{}")
    for _ in range(3):
        file.prendre("worker", MIDI)
        file.relacher_abandonnes(MIDI + timedelta(hours=3))
    assert file.lire("j").statut == "echec"


def test_un_job_abandonne_dont_la_demande_attend_deja_passe_en_echec() -> None:
    """La même demande, déposée pendant le job (AXE-921), refera le travail."""
    file = FileMemoire()
    file.deposer("j", "ten", TYPE_SYNCHRO, "{}")
    file.prendre("worker", MIDI)
    file.deposer("k", "ten", TYPE_SYNCHRO, "{}")
    file.relacher_abandonnes(MIDI + timedelta(hours=3))
    assert (file.lire("j").statut, file.lire("k").statut) == ("echec", "en_attente")


def test_un_rapprochement_recent_ou_en_cours_n_est_pas_relance() -> None:
    maintenant = datetime(2026, 11, 16, 12, tzinfo=UTC)
    fini = Job(
        "j", "ten", TYPE_RAPPROCHEMENT_ROLLEE, "{}", 10, "fait", 1, None, 1, termine_le=maintenant
    )
    assert deja_couvert(fini, maintenant + timedelta(minutes=9))
    assert not deja_couvert(fini, maintenant + timedelta(minutes=10))
    en_cours = Job("k", "ten", TYPE_RAPPROCHEMENT_ROLLEE, "{}", 10, "en_cours", 1, "worker", 2)
    assert deja_couvert(en_cours, maintenant + timedelta(hours=1))
    assert not deja_couvert(None, maintenant)
