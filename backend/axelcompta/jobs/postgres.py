"""La prise d'un job, en SQL. Le worker tourne avec le rôle propriétaire.

`FOR UPDATE SKIP LOCKED` : deux workers ne prennent pas la même ligne
(ADR-002). Pas de test d'intégration ici : la sémantique est celle de
`FileMemoire`, cette requête est le pendant Postgres.
"""

REQUETE_PRENDRE = """
SELECT id FROM jobs
WHERE statut = 'en_attente'
ORDER BY priorite, cree_le
FOR UPDATE SKIP LOCKED
LIMIT 1
"""
