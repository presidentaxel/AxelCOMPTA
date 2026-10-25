"""File de jobs PostgreSQL SKIP LOCKED (ADR-002), d'abord en mémoire.

Les types couvrent ce que le cron lançait à la main : synchro Digifactory,
notifications, passage du modèle. Le module ne les exécute pas : il ne
dépend que de core, le worker reçoit les handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

TYPES = frozenset({"synchro_digifactory", "notifier", "ml"})
TENTATIVES_MAX = 3


class TypeInconnu(ValueError):
    """Le type de job n'est pas un des trois prévus."""


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    tenant_id: str
    type: str
    payload: str
    priorite: int
    statut: str
    tentatives: int
    verrou_par: str | None
    ordre: int


class FileMemoire:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._ordre = 0

    def deposer(
        self,
        identifiant: str,
        tenant_id: str,
        type_job: str,
        payload: str,
        priorite: int = 10,
    ) -> Job:
        if type_job not in TYPES:
            raise TypeInconnu(type_job)
        self._ordre += 1
        job = Job(
            id=identifiant,
            tenant_id=tenant_id,
            type=type_job,
            payload=payload,
            priorite=priorite,
            statut="en_attente",
            tentatives=0,
            verrou_par=None,
            ordre=self._ordre,
        )
        self._jobs[identifiant] = job
        return job

    def prendre(self, worker: str) -> Job | None:
        candidats = [job for job in self._jobs.values() if job.statut == "en_attente"]
        if not candidats:
            return None
        choisi = min(candidats, key=lambda job: (job.priorite, job.ordre))
        pris = replace(
            choisi,
            statut="en_cours",
            verrou_par=worker,
            tentatives=choisi.tentatives + 1,
        )
        self._jobs[pris.id] = pris
        return pris

    def terminer(self, identifiant: str) -> None:
        self._jobs[identifiant] = replace(self._jobs[identifiant], statut="fait", verrou_par=None)

    def echouer(self, identifiant: str) -> None:
        actuel = self._jobs[identifiant]
        statut = "echec" if actuel.tentatives >= TENTATIVES_MAX else "en_attente"
        self._jobs[identifiant] = replace(actuel, statut=statut, verrou_par=None)

    def lire(self, identifiant: str) -> Job:
        return self._jobs[identifiant]
