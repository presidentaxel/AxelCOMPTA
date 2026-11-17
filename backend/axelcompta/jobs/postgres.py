"""La prise d'un job, en SQL. Le worker tourne avec le rôle propriétaire.

`FOR UPDATE SKIP LOCKED` : deux workers ne prennent pas la même ligne
(ADR-002). `FilePostgres` (AXE-845) : la file réelle, testée contre Postgres.
Sémantique de `FileMemoire`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from axelcompta.core.rls import appliquer_rls

from .file import DELAI_ABANDON, ERREUR_ABANDON, TENTATIVES_MAX, TYPES, Job, TypeInconnu

REQUETE_PRENDRE = """
SELECT id FROM jobs
WHERE statut = 'en_attente'
ORDER BY priorite, cree_le
FOR UPDATE SKIP LOCKED
LIMIT 1
"""


REQUETE_ECHOUER = """
UPDATE jobs SET statut = d.statut, verrou_par = NULL, derniere_erreur = :e,
  termine_le = CASE WHEN d.statut = 'echec' THEN now() END
FROM (
  SELECT CASE WHEN j.tentatives >= :max OR EXISTS (
      SELECT 1 FROM jobs k WHERE k.id <> j.id AND k.statut = 'en_attente'
        AND k.tenant_id = j.tenant_id AND k.type = j.type AND k.payload = j.payload
    ) THEN 'echec' ELSE 'en_attente' END AS statut
  FROM jobs j WHERE j.id = :id
) d
WHERE jobs.id = :id
RETURNING jobs.statut
"""


REQUETE_ABANDONNES = """
SELECT id FROM jobs
WHERE statut = 'en_cours' AND coalesce(pris_le, cree_le) < :limite
ORDER BY cree_le
FOR UPDATE SKIP LOCKED
"""


class FilePostgres:
    """La file en base (AXE-845). Deux demandes identiques (portefeuille,
    type, payload) **en attente** n'en font qu'une (index unique partiel
    `jobs_une_demande_en_attente`). Une demande faite pendant qu'un job tourne
    attend son tour : ce job a déjà lu ce qu'il devait faire (AXE-921)."""

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
        job = self._en_attente(tenant_id, type_job, payload) or self.dernier(tenant_id, type_job)
        assert job is not None
        return job

    def _en_attente(self, tenant_id: str, type_job: str, payload: str) -> Job | None:
        with self._engine.connect() as connexion:
            appliquer_rls(connexion)
            ligne = connexion.execute(
                text(
                    "SELECT * FROM jobs WHERE tenant_id = :t AND type = :type "
                    "AND payload = :payload AND statut = 'en_attente' "
                    "ORDER BY cree_le DESC LIMIT 1"
                ),
                {"t": tenant_id, "type": type_job, "payload": payload},
            ).first()
        return None if ligne is None else _job(ligne)

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
                    "UPDATE jobs SET statut = 'en_cours', verrou_par = :w, pris_le = now(), "
                    "tentatives = tentatives + 1 WHERE id = :id RETURNING *"
                ),
                {"w": worker, "id": ligne.id},
            ).one()
        return _job(pris)

    def terminer(self, identifiant: str, resultat: str) -> None:
        self._fermer(identifiant, "fait", resultat=resultat)

    def echouer(self, identifiant: str, erreur: str) -> bool:
        """Réessayé plus tard, sauf au dernier essai, ou si la même demande
        attend déjà (AXE-921) : elle refera le travail, et deux demandes
        identiques en attente sont interdites par l'index. Rend True quand
        le job est clos, False quand il repart en attente."""
        with self._engine.begin() as connexion:
            ligne = connexion.execute(
                text(REQUETE_ECHOUER), {"id": identifiant, "e": erreur, "max": TENTATIVES_MAX}
            ).one()
        return str(ligne.statut) == "echec"

    def relacher_abandonnes(self, delai: timedelta = DELAI_ABANDON) -> list[str]:
        """AXE-958 : un job `en_cours` pris depuis plus de `delai` a perdu
        son worker. Il suit la règle d'un échec : de nouveau en attente s'il
        reste des essais et qu'aucune demande identique n'attend, sinon en
        échec. Un job pris avant `pris_le` retombe sur `cree_le`."""
        with self._engine.begin() as connexion:
            ids = [
                ligne.id
                for ligne in connexion.execute(
                    text(REQUETE_ABANDONNES), {"limite": datetime.now(UTC) - delai}
                )
            ]
            for identifiant in ids:
                connexion.execute(
                    text(REQUETE_ECHOUER),
                    {"id": identifiant, "e": ERREUR_ABANDON, "max": TENTATIVES_MAX},
                ).one()
        return ids

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
        pris_le=ligne.pris_le,
    )
