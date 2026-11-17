"""AXE-959 : le worker et les tâches planifiées préviennent Sentry, sans
réseau ici (envois injectés)."""

from __future__ import annotations

from typing import Any

from axelcompta.surveillance import (
    MONITEUR_TACHES,
    MUETTE,
    Sentinelle,
    sentinelle_sentry,
)


class Envois:
    def __init__(self) -> None:
        self.check_ins: list[dict[str, Any]] = []
        self.messages: list[str] = []
        self.exceptions: list[tuple[BaseException, dict[str, str]]] = []

    def check_in(self, **kwargs: Any) -> str:
        self.check_ins.append(kwargs)
        return "ci-1"

    def sentinelle(self) -> Sentinelle:
        return Sentinelle(
            check_in=self.check_in,
            message=self.messages.append,
            exception=lambda e, t: self.exceptions.append((e, t)),
        )


def test_un_passage_reussi_fait_deux_check_ins_sans_message() -> None:
    envois = Envois()
    sentinelle = envois.sentinelle()
    passage = sentinelle.debut_taches()
    sentinelle.fin_taches(passage, False, ["TENANT synchro : 3 ok, 0 en échec"])
    statuts = [(c["monitor_slug"], c["status"]) for c in envois.check_ins]
    assert statuts == [(MONITEUR_TACHES, "in_progress"), (MONITEUR_TACHES, "ok")]
    assert envois.check_ins[1]["check_in_id"] == "ci-1"
    assert envois.check_ins[0]["monitor_config"]["schedule"]["value"] == "7 * * * *"
    assert envois.messages == []


def test_un_passage_en_echec_passe_le_moniteur_en_erreur_et_dit_pourquoi() -> None:
    envois = Envois()
    sentinelle = envois.sentinelle()
    sentinelle.fin_taches(
        sentinelle.debut_taches(), True, ["TENANT synchro : échec (Timeout: Digifactory)"]
    )
    assert envois.check_ins[-1]["status"] == "error"
    assert len(envois.messages) == 1
    assert "Digifactory" in envois.messages[0]


def test_un_job_en_echec_part_avec_son_type() -> None:
    envois = Envois()
    erreur = RuntimeError("Digifactory injoignable")
    envois.sentinelle().job_en_echec(erreur, "synchro_digifactory", "job-1")
    assert envois.exceptions == [(erreur, {"job_type": "synchro_digifactory", "job_id": "job-1"})]


def test_sans_dsn_rien_n_est_envoye(monkeypatch: Any) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    sentinelle = sentinelle_sentry()
    assert sentinelle is MUETTE
    passage = sentinelle.debut_taches()
    sentinelle.fin_taches(passage, True, ["échec"])
    sentinelle.job_en_echec(RuntimeError("x"), "rappels", "j")
