# ADR-002 — File de jobs : PostgreSQL SKIP LOCKED vs Redis/RQ

**Date :** 2026-06-16
**Statut :** accepté le 2026-10-25 — option A (PostgreSQL `SKIP LOCKED`), posée dans `backend/axelcompta/jobs/` (AXE-442, migration `b6d1e9a43c20`). Pas encore utilisée : le cron `axelcompta.taches` reste le mécanisme réel. Premier usage prévu : l'envoi des rappels (AXE-808).

## Contexte

Le système a besoin d'exécuter des jobs asynchrones : import de transactions, appels LLM, génération de FEC, génération de PDF, envoi d'emails de relance, clôtures différées. Ces jobs doivent être idempotents, traçables, et ne jamais perdre de travail.

## Options

**Option A — PostgreSQL avec SKIP LOCKED** (démarrage recommandé)
- Une table `jobs` avec colonnes : `id`, `type`, `payload`, `status`, `priority`, `scheduled_at`, `locked_by`, `locked_at`, `attempts`, `last_error`.
- Les workers sélectionnent le prochain job avec `SELECT ... FOR UPDATE SKIP LOCKED`.
- Avantages : aucune infrastructure supplémentaire, transactions ACID (un job est pris ou pas, jamais les deux), visibilité directe en SQL, monitoring simple.
- Inconvénients : throughput limité (acceptable pour 200 dossiers), polling (latence de quelques secondes entre soumission et exécution).

**Option B — Redis + RQ (ou Celery)**
- Broker Redis dédié, workers Celery/RQ.
- Avantages : throughput élevé, support natif des priorités, écosystème mature.
- Inconvénients : infrastructure supplémentaire à opérer, risque de perte de message si Redis redémarre sans persistance configurée, cohérence avec Postgres nécessite une attention particulière (le job peut être marqué "fait" dans Redis mais pas en base, ou vice-versa).

## Décision provisoire

**Démarrer avec PostgreSQL SKIP LOCKED.** Aucune infrastructure supplémentaire, comportement transactionnel garanti. Migrer vers Redis uniquement si le volume ou les contraintes de latence l'exigent.

La table `jobs` inclut un champ `priority` (entier, plus bas = plus prioritaire) pour supporter le cas de clôture prioritaire (doc 12, clôture intelligente) : un bouton "priorité maximale" sur un dossier passe son job à `priority = 0`.

## Critères de réexamen

Revoir cette décision si : throughput > 1 000 jobs/heure en pic, ou si la latence polling (< 5 s) devient inacceptable pour un cas d'usage critique.
