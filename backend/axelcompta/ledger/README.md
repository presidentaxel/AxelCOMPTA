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

- `banque.py` — lecture des lignes de banque d'une écriture (`ligne_banque`,
  `montant_bancaire`, `comptes_hors_banque`, `est_reclassement_bancaire`).
  Depuis AXE-832, une écriture bancaire porte 512 **ou un sous-compte 512x** :
  on ne compare jamais un compte à la chaîne `"512"`, on passe par
  `core.pcg.est_compte_banque`.

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
- `periodes.py` (AXE-806, doc 06 I4) — aucune écriture datée dans un
  exercice clos : `PeriodeClose` (API : 409), `date_de_report()` (premier
  jour de l'exercice ouvert : début d'exercice du dossier, AXE-838). `LedgerService.periodes_closes()` lit
  `exercices_clos` ; le trigger `ecritures_hors_periode_close` (migration
  `f1a6c3e9d257`) refuse aussi en base. Une opération bancaire tardive
  datée dans un exercice clos part en quarantaine (`periode_close`).
- **I3, numérotation** (AXE-807) — une séquence par dossier et par exercice,
  tous journaux confondus, dans l'ordre de validation : `numero` et
  `valide_le` posés par le trigger `ecritures_numerotation` (migration
  `a3e8c1f5b297`), sans trou (compteur dans la transaction). Le FEC lit ces
  numéros (`filings/fec.ordre_fec`) et contrôle la chronologie sur
  `ValidDate`.
- `balance.py` (AXE-807, I7) — contrôle quotidien de la balance par journal
  et par dossier (`axelcompta.taches`, à 3 h) : écart → alerte Sentry, ligne
  au journal, `balance_desequilibree_total`. Aucune correction automatique.
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
