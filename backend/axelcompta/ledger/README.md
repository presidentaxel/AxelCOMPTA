# ledger/ ❤️

Le moteur comptable **pur** : écritures, journaux, balance, immobilisations,
TVA. Le cœur du produit — c'est le module qui doit être juste avant tout le
reste.

**Dépendances : `core` uniquement.** Jamais `categorize`, jamais `ml`, jamais
`api` (règle vérifiée par import-linter en CI, doc 03 §3).

## Invariants absolus (doc 06 §1 — violation = bug bloquant, jamais contournable)

- Montants toujours en centimes (`int`), jamais de `float`.
- Toute écriture équilibrée (débit = crédit) ou rejetée, jamais persistée
  déséquilibrée.
- Immutabilité : une écriture validée ne se modifie pas, elle se contre-passe.
  **En base depuis le 2026-09-24** : trigger sur `ecritures` et
  `lignes_ecriture` (migration `a91c4e2b7d10`). `contrepassation.py` construit
  l'inverse (journal OD, id `{origine}:contrepassation`) ; `workflow/synchro.py`
  l'enregistre quand Digifactory modifie ou supprime une transaction déjà
  comptabilisée.

## Fichiers

- `models.py` — domaine pur (`Ecriture`, `LigneEcriture`, `Journal`, `Sens`).
- `invariants.py` — `verifier_equilibre` : pur, sans I/O, la seule autorité sur
  l'équilibre débit/crédit.
- `service.py` — `LedgerService`, la façade abstraite (seule chose que `api`
  a le droit d'importer, doc 03 §3).
- `memory.py` — `InMemoryLedgerService` : implémentation en mémoire pour la
  démo (doc 17 semaine 0), sans Postgres.
- `orm.py` / `repository.py` — `PostgresLedgerService` : implémentation
  réelle contre Postgres (SQLAlchemy Core). `orm.py` définit les tables,
  séparé de `models.py` pour garder le domaine pur (doc 08 §2.1).
- `contrepassation.py` — `contrepasser()` (**fait, 2026-09-24**, doc 06 I2) :
  pure, sans I/O. Inverse les sens, garde les montants, journal `OD`.

## Statuts

- **Fait** : `verifier_equilibre`, `LedgerService` mémoire et Postgres,
  écritures validées immuables en base (I2, 2026-09-24), contre-passation
  (`contrepassation.py`), ventilation TVA des settlements (doc 13 §5.3).
- **Au 2026-11-05, invariants non tenus** : I3 numérotation continue en
  base et I7 contrôle quotidien (AXE-807), I4 aucune écriture dans un
  exercice clos (AXE-806).
- **V1 (doc 12, phase 1.2-1.3)** : moteur complet, immobilisations,
  rapprochement bancaire (doc 06 §4), tous les templates du pack VTC (doc 06 §3).

## Doc de référence

[doc 06](../../../docs/06-moteur-comptable.md) (référence complète du module),
[doc 13 §5](../../../docs/13-integrations-plateformes.md#5-génération-décritures-depuis-un-settlement-réconcilié) (templates de settlement),
[doc 17 §7](../../../docs/archive/17-plan-demo-journal-2026-09.md#7-golden-test-de-sortie).
