from __future__ import annotations

import base64

import pytest

from axelcompta.jobs.executer import executer
from axelcompta.jobs.file import FileMemoire, TypeInconnu
from axelcompta.jobs.postgres import REQUETE_PRENDRE
from axelcompta.tenants.mfa import code_totp, secret_aleatoire, verifier_totp
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


def test_vecteur_rfc_6238() -> None:
    secret = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")
    assert code_totp(secret, 59) == "287082"
    assert verifier_totp(secret, "287082", 59)
    assert not verifier_totp(secret, "000000", 59)
    assert len(secret_aleatoire()) > 0


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
