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
- **V1 (doc 12, phase 1.1 + 3)** : auth/MFA, permissions par rôle,
  isolation multi-tenant appliquée au niveau des routes.

## Doc de référence

[doc 03 §7](../../../docs/03-architecture.md#7-auth-rôles-multi-tenant),
[doc 17 §9](../../../docs/archive/17-plan-demo-journal-2026-09.md#9-semaines-et-jalons) (API de démo : `demo_api.py`, pas ce module),
[doc 19](../../../docs/19-parcours-utilisateur.md).
