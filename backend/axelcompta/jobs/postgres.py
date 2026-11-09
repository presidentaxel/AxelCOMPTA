"""La prise d'un job, en SQL. Le worker tourne avec le rôle propriétaire.

`FOR UPDATE SKIP LOCKED` : deux workers ne prennent pas la même ligne
(ADR-002). `FilePostgres` (AXE-845) : la file réelle, testée contre Postgres.
Sémantique de `FileMemoire`.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from axelcompta.core.rls import appliquer_rls

from .file import TENTATIVES_MAX, TYPES, Job, TypeInconnu

REQUETE_PRENDRE = """
SELECT id FROM jobs
WHERE statut = 'en_attente'
ORDER BY priorite, cree_le
FOR UPDATE SKIP LOCKED
LIMIT 1
"""


class FilePostgres:
    """La file en base (AXE-845). Au plus une demande active (en attente ou
    en cours) par portefeuille et par type : redemander pendant qu'une
    synchro tourne rend la demande en cours, sans en créer une seconde
    (index unique partiel `jobs_un_actif_par_type`)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def demander(self, tenant_id: str, type_job: str, payload: str = "{}") -> Job:
        if type_job not in TYPES:
            raise TypeInconnu(type_job)
        with self._engine.begin() as connexion:
            appliquer_rls(connexion)
            connexion.execute(
                text(
                    """
                    INSERT INTO jobs (id, tenant_id, type, payload, statut, priorite,
                                      tentatives, cree_le)
                    VALUES (:id, :t, :type, :payload, 'en_attente', 10, 0, now())
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"id": str(uuid.uuid4()), "t": tenant_id, "type": type_job, "payload": payload},
            )
        job = self.dernier(tenant_id, type_job)
        assert job is not None
        return job

    def dernier(self, tenant_id: str, type_job: str) -> Job | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                text(
                    "SELECT * FROM jobs WHERE tenant_id = :t AND type = :type "
                    "ORDER BY cree_le DESC LIMIT 1"
                ),
                {"t": tenant_id, "type": type_job},
            ).first()
        return None if ligne is None else _job(ligne)

    def prendre(self, worker: str) -> Job | None:
        with self._engine.begin() as connexion:
            ligne = connexion.execute(text(REQUETE_PRENDRE)).first()
            if ligne is None:
                return None
            pris = connexion.execute(
                text(
                    "UPDATE jobs SET statut = 'en_cours', verrou_par = :w, "
                    "tentatives = tentatives + 1 WHERE id = :id RETURNING *"
                ),
                {"w": worker, "id": ligne.id},
            ).one()
        return _job(pris)

    def terminer(self, identifiant: str, resultat: str) -> None:
        self._fermer(identifiant, "fait", resultat=resultat)

    def echouer(self, identifiant: str, erreur: str) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                text(
                    "UPDATE jobs SET statut = CASE WHEN tentatives >= :max THEN 'echec' "
                    "ELSE 'en_attente' END, verrou_par = NULL, derniere_erreur = :e, "
                    "termine_le = CASE WHEN tentatives >= :max THEN now() END WHERE id = :id"
                ),
                {"id": identifiant, "e": erreur, "max": TENTATIVES_MAX},
            )

    def _fermer(self, identifiant: str, statut: str, resultat: str) -> None:
        with self._engine.begin() as connexion:
            connexion.execute(
                text(
                    "UPDATE jobs SET statut = :s, verrou_par = NULL, resultat = :r, "
                    "termine_le = now() WHERE id = :id"
                ),
                {"id": identifiant, "s": statut, "r": resultat},
            )


def _job(ligne: Row[Any]) -> Job:
    return Job(
        id=ligne.id,
        tenant_id=ligne.tenant_id,
        type=ligne.type,
        payload=ligne.payload,
        priorite=ligne.priorite,
        statut=ligne.statut,
        tentatives=ligne.tentatives,
        verrou_par=ligne.verrou_par,
        ordre=0,
        resultat=ligne.resultat,
        derniere_erreur=ligne.derniere_erreur,
        cree_le=ligne.cree_le,
        termine_le=ligne.termine_le,
    )
