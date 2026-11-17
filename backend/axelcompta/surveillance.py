"""Prévenir quand le worker ou les tâches planifiées échouent ou ne passent
plus (AXE-959).

- Sentry démarre au début de chaque passage, si `SENTRY_DSN` est posé
  et que `ENV` n'est pas `dev`.
- Un job du worker en échec part dans Sentry, avec son type.
- Les tâches planifiées font un check-in sur le moniteur Sentry Crons
  `axelcompta-taches` : au début, puis ok ou erreur à la fin. Sentry alerte
  si un passage manque, dure trop longtemps ou échoue. Un passage en échec
  envoie aussi un message qui reprend le bilan.

Sans DSN, `Sentinelle` ne fait rien : le reste du code l'appelle sans test.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from axelcompta.api.observabilite import installer_sentry

MONITEUR_TACHES = "axelcompta-taches"
# Même calendrier que `backend/docker/crontab` : minute 7, fuseau UTC.
CONFIG_MONITEUR_TACHES: dict[str, Any] = {
    "schedule": {"type": "crontab", "value": "7 * * * *"},
    "timezone": "UTC",
    # Minutes : le passage peut démarrer jusqu'à 15 min en retard, et doit
    # finir avant le suivant.
    "checkin_margin": 15,
    "max_runtime": 55,
    "failure_issue_threshold": 1,
    "recovery_threshold": 1,
}

CheckIn = Callable[..., str | None]
Message = Callable[[str], None]
Exception_ = Callable[[BaseException, dict[str, str]], None]


@dataclass(frozen=True, slots=True)
class Passage:
    check_in_id: str | None
    debut: float


@dataclass(frozen=True, slots=True)
class Sentinelle:
    """Les envois, injectés pour être testés sans réseau."""

    check_in: CheckIn | None = None
    message: Message | None = None
    exception: Exception_ | None = None

    def debut_taches(self) -> Passage:
        identifiant = None
        if self.check_in is not None:
            identifiant = self.check_in(
                monitor_slug=MONITEUR_TACHES,
                status="in_progress",
                monitor_config=CONFIG_MONITEUR_TACHES,
            )
        return Passage(identifiant, time.monotonic())

    def fin_taches(self, passage: Passage, echec: bool, lignes: list[str]) -> None:
        if echec and self.message is not None:
            self.message("Tâches planifiées : passage en échec\n" + "\n".join(lignes))
        if self.check_in is not None:
            self.check_in(
                monitor_slug=MONITEUR_TACHES,
                check_in_id=passage.check_in_id,
                status="error" if echec else "ok",
                duration=time.monotonic() - passage.debut,
                monitor_config=CONFIG_MONITEUR_TACHES,
            )

    def job_en_echec(self, erreur: BaseException, type_job: str, job_id: str) -> None:
        if self.exception is not None:
            self.exception(erreur, {"job_type": type_job, "job_id": job_id})


MUETTE = Sentinelle()


def sentinelle_sentry() -> Sentinelle:
    """Branchée sur Sentry si `SENTRY_DSN` est posé, muette sinon.
    Muette aussi quand `ENV=dev`."""
    if not installer_sentry():
        return MUETTE
    import sentry_sdk
    from sentry_sdk.crons import capture_checkin

    def message(texte: str) -> None:
        sentry_sdk.capture_message(texte, level="error")

    def exception(erreur: BaseException, etiquettes: dict[str, str]) -> None:
        with sentry_sdk.new_scope() as portee:
            for cle, valeur in etiquettes.items():
                portee.set_tag(cle, valeur)
            sentry_sdk.capture_exception(erreur)

    return Sentinelle(check_in=capture_checkin, message=message, exception=exception)
