# api/

Routes FastAPI, auth, permissions. **Aucune logique métier ici** — n'importe
que les façades publiques de chaque module (`module/service.py`, règle
vérifiée par import-linter en CI, doc 03 §3).

**Dépendances :** façades publiques de tous les modules métier.

## Statuts

- **Démo (doc 17, pivot 2026-09-06)** : `create_app` est le point
  d'entrée (`uvicorn axelcompta.api.app:app`). Il délègue encore à
  `axelcompta.demo_api`, le composition root, et ajoute `GET /sante`.
  Les corps de routes restent là-bas jusqu'à l'extraction de chaque
  façade (`module/service.py`). Rien de métier n'est copié ici.
- **Au 2026-11-10** : `GET /metrics` (Prometheus, AXE-426), fermé sans
  `METRICS_TOKEN` (AXE-810). Rôles lecture, membre, admin appliqués par
  route et dans l'interface (AXE-701), et `expert_comptable` (AXE-800).
  MFA demandée à la connexion (jeton `aal2`, dépendance
  `exiger_double_authentification`) et journal des connexions et exports
  (AXE-812). Compte de test en lecture seule (en-tête `X-Dossier`,
  AXE-822). `api/erreurs.py` : un seul gestionnaire pour les erreurs
  métier, 4xx avec leur phrase (AXE-839). Au démarrage, l'API vérifie que
  la base est à la dernière migration (AXE-841).
- **V1 (doc 12)** : extraire les routes de `demo_api.py` vers les façades
  et renommer les fichiers `demo_*` (AXE-840).

## Doc de référence

[doc 03 §7](../../../docs/03-architecture.md#7-auth-rôles-multi-tenant),
[doc 17 §9](../../../docs/archive/17-plan-demo-journal-2026-09.md#9-semaines-et-jalons) (API de démo : `demo_api.py`, pas ce module),
[doc 19](../../../docs/19-parcours-utilisateur.md).
