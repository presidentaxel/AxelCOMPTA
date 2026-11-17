"""File de jobs PostgreSQL SKIP LOCKED (ADR-002), d'abord en mémoire.

Les types couvrent ce que le cron lançait à la main : synchro Digifactory,
notifications, passage du modèle. Le module ne les exécute pas : il ne
dépend que de core, le worker reçoit les handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

TYPE_SYNCHRO = "synchro_digifactory"
# Création des dossiers d'un fichier validé (AXE-809).
TYPE_IMPORT_DOSSIERS = "import_dossiers"
# Envoi des rappels par l'e-mail ou le SMS du gestionnaire (AXE-808).
TYPE_RAPPELS = "rappels"
# Webhooks Rollee reçus, à traiter (AXE-820).
TYPE_ROLLEE = "rollee"
# Remplir la carte Rollee et relier les users, hors de la requête HTTP.
TYPE_RAPPROCHEMENT_ROLLEE = "rapprochement_rollee"
TYPES = frozenset(
    {
        TYPE_SYNCHRO,
        TYPE_IMPORT_DOSSIERS,
        TYPE_RAPPELS,
        TYPE_ROLLEE,
        TYPE_RAPPROCHEMENT_ROLLEE,
        "notifier",
        "ml",
    }
)
TENTATIVES_MAX = 3
# AXE-958 : un job `en_cours` depuis plus longtemps a perdu son worker
# (conteneur remplacé au déploiement, processus tué). Le plus long observé
# en production : une synchro de 15 minutes.
DELAI_ABANDON = timedelta(hours=2)
# Un rapprochement qui vient de finir, ou qui tourne, n'est pas relancé :
# cinq clics d'affilée reparcouraient les mêmes comptes.
DELAI_SANS_RELANCER = timedelta(minutes=10)
ERREUR_ABANDON = (
    "Abandonné : le worker s'est arrêté pendant le travail (redéploiement ?). "
    "Relancé automatiquement s'il reste des essais."
)


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
    # Suivi affiché au gestionnaire (AXE-845) : résumé ou erreur en clair.
    resultat: str | None = None
    derniere_erreur: str | None = None
    cree_le: datetime | None = None
    termine_le: datetime | None = None
    # AXE-958 : heure de prise par le worker.
    pris_le: datetime | None = None

    @property
    def actif(self) -> bool:
        return self.statut in ("en_attente", "en_cours")


def deja_couvert(
    job: Job | None, maintenant: datetime, delai: timedelta = DELAI_SANS_RELANCER
) -> bool:
    """Vrai si ce job tourne encore, ou s'il s'est terminé dans `delai`."""
    if job is None:
        return False
    if job.actif:
        return True
    return (
        job.statut == "fait" and job.termine_le is not None and maintenant - job.termine_le < delai
    )


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

    def prendre(self, worker: str, maintenant: datetime | None = None) -> Job | None:
        candidats = [job for job in self._jobs.values() if job.statut == "en_attente"]
        if not candidats:
            return None
        choisi = min(candidats, key=lambda job: (job.priorite, job.ordre))
        pris = replace(
            choisi,
            statut="en_cours",
            verrou_par=worker,
            tentatives=choisi.tentatives + 1,
            pris_le=maintenant or datetime.now(UTC),
        )
        self._jobs[pris.id] = pris
        return pris

    def terminer(self, identifiant: str) -> None:
        self._jobs[identifiant] = replace(self._jobs[identifiant], statut="fait", verrou_par=None)

    def echouer(self, identifiant: str) -> bool:
        """Remet en attente s'il reste un essai. Rend True quand le job est clos."""
        actuel = self._jobs[identifiant]
        doublon = any(
            j.id != identifiant
            and j.statut == "en_attente"
            and (j.tenant_id, j.type, j.payload) == (actuel.tenant_id, actuel.type, actuel.payload)
            for j in self._jobs.values()
        )
        statut = "echec" if actuel.tentatives >= TENTATIVES_MAX or doublon else "en_attente"
        self._jobs[identifiant] = replace(actuel, statut=statut, verrou_par=None)
        return statut == "echec"

    def relacher_abandonnes(
        self, maintenant: datetime, delai: timedelta = DELAI_ABANDON
    ) -> list[str]:
        """AXE-958 : comme `FilePostgres.relacher_abandonnes`."""
        abandonnes = [
            job.id
            for job in self._jobs.values()
            if job.statut == "en_cours"
            and (job.pris_le or job.cree_le or maintenant) < maintenant - delai
        ]
        for identifiant in abandonnes:
            self.echouer(identifiant)
        return abandonnes

    def lire(self, identifiant: str) -> Job:
        return self._jobs[identifiant]

    def demander(self, tenant_id: str, type_job: str, payload: str = "{}") -> Job:
        """Comme `FilePostgres.demander` : la même demande en attente si elle
        existe. Un job en cours ne l'absorbe pas (AXE-921)."""
        en_attente = next(
            (
                j
                for j in self._jobs.values()
                if j.tenant_id == tenant_id
                and j.type == type_job
                and j.payload == payload
                and j.statut == "en_attente"
            ),
            None,
        )
        if en_attente is not None:
            return en_attente
        job = self.deposer(f"job-{self._ordre + 1}", tenant_id, type_job, payload)
        job = replace(job, cree_le=datetime.now(UTC))
        self._jobs[job.id] = job
        return job

    def dernier(self, tenant_id: str, type_job: str) -> Job | None:
        candidats = [
            j for j in self._jobs.values() if j.tenant_id == tenant_id and j.type == type_job
        ]
        return max(candidats, key=lambda j: j.ordre) if candidats else None


class DemandesDeJobs(Protocol):
    """Ce dont l'API a besoin : déposer une demande et suivre la dernière."""

    def demander(self, tenant_id: str, type_job: str, payload: str = "{}") -> Job: ...

    def dernier(self, tenant_id: str, type_job: str) -> Job | None: ...
