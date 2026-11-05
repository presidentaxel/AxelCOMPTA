# workflow/

Validation, circuit de relecture humaine, signature électronique. C'est le
seul module autorisé à transformer une `ProposedEntry` (sortie de
`categorize/`) en écriture réelle via `ledger/`.

**Dépendances :** `core`, `categorize`, `ingestion` (types transaction),
`ledger`.

## Fichiers

- `auto_accept.py` — `construire_ecriture_categorisee()` (**fait, semaine 2**) :
  stand-in minimal, accepte toute `ProposedEntry` sans validation humaine et
  construit une écriture 512/compte-catégorie (pas de ventilation TVA — ça,
  c'est réservé au settlement plateforme, `ingestion/ecritures_settlement.py`).
  **Pas l'architecture cible** : la file de revue (doc 05 §5) couvre les
  cas « à trancher » (`revue.py`) ; ceci satisfait la règle de dépendance
  (« seul workflow transforme une ProposedEntry en écriture ») pour les
  écritures acceptées sans clic humain.
- `decisions.py` — `DecisionHumaine`, `AnnotationDev`, `DecisionRepository`
  (**fait, 2026-09-07, doc 17 §9 bloc A**) : modèle de la vraie décision
  humaine (immuable, doc 05 §5 précisé) et de l'annotation dev séparée pour
  le réentraînement — ne remplace pas `auto_accept.py`, prépare le
  branchement de l'écran de revue (bloc C) par-dessus.
- `decisions_memory.py` — `InMemoryDecisionRepository` (**fait,
  2026-09-07**) : implémentation en mémoire, pour les tests unitaires
  rapides — comme `ledger/memory.py` pour le ledger.
- `orm.py` / `decisions_postgres.py` — `PostgresDecisionRepository`
  (**fait, 2026-09-07**) : la vraie persistance (doc 17 §9 bloc A). Deux
  tables (`decisions_humaines`, `annotations_dev`), append-only, FK
  vers `dossiers` et `ecritures` depuis le 2026-09-22 (migration
  `7cd5053e8209` ; elles manquaient tant que ces tables n'étaient pas
  peuplées, détail dans `orm.py`). Migration
  `55cf8c93e5bf` (`migrations/versions/`). Testé contre un vrai conteneur
  (`tests/integration/test_decisions_repository.py`, comme
  `test_ledger_repository.py` pour le ledger). Depuis le 2026-09-24,
  `UPDATE`/`DELETE` sont refusés en base sur `decisions_humaines`
  (migration `d8b41c6e0a27`) et chaque insertion écrit `journal_audit`
  (`audit.py`, migration `c2f91ab84e30`).
- `signature.py` / `signature_postgres.py` — signature greffe append-only.
  Même verrou en base sur `documents_signes` (2026-09-24) et même ligne
  d'audit à l'enregistrement.
- `audit.py` — `noter()` : insert seul, dans la transaction déjà ouverte.
  Champs : dossier, type d'acte (`decision` ou `signature`), référence,
  acteur, horodatage. Pas de libellé, pas de PDF.

## Contenu prévu (V1)

- Circuit de validation avant écriture définitive.
- Signature électronique qualifiée — prestataire à choisir (ADR-004, devis
  Yousign/Docusign). La démo a un tampon et une persistance Postgres
  (`documents_signes`, verrouillée le 2026-09-24) ; `qualifie` reste faux.
- Journal d'audit des consultations et des exports (doc 10). Décisions et
  signatures sont déjà tracées (`audit.py`).

## Ventilation bancaire (AXE-832)

- `synchro.py` pose chaque opération sur le sous-compte 512x de son compte
  bancaire quand on lui passe le registre `comptes_bancaires`.
- `ventilation_bancaire.py` reprend les écritures restées au 512 : une
  écriture de reclassement par opération (journal OD, `{id}:ventilation-banque`,
  512x d'un côté, 512 de l'autre), sans toucher l'originale (I2) ni la
  contre-passer (la synchro y verrait une transaction modifiée). Rejouable.
  Lancement : `python scripts/ventiler_comptes_bancaires.py --tenant … [--appliquer]`.

## Statuts

- **Démo (doc 17 §9)** : `auto_accept.py` reste actif pour les cas
  nominaux (Karim, Yanis). **Bloc A et C finis (2026-09-07)** : la file de
  revue est réelle de bout en bout — `demo_api.py` expose
  `POST .../decision`, le clic dans l'UI déclenche vraiment
  `revue.py`/`decisions_postgres.py`, testé en HTTP réel (`curl`) et dans
  un vrai navigateur (clic → Postgres → rafraîchissement). `auto_accept.py`
  n'est donc plus la seule voie : Sophie passe maintenant par la vraie
  décision humaine, Karim/Yanis restent sur le stand-in (rien à trancher
  chez eux dans la démo).
- `propositions.py` / `propositions_postgres.py` (**fait, 2026-09-21**) :
  conserve la proposition d'origine du pipeline par écriture (étage,
  confiance), nécessaire à la file de revue depuis que le ledger est
  persisté et non recalculé. Table `propositions_categorisation`.
- `notifications.py` / `notifications_postgres.py` (**fait, 2026-09-22 ;
  internes depuis le 2026-09-26**) : notification « opérations à confirmer »
  (doc 19 §5.2) posée dans l'application, regroupée par dossier,
  anti-harcèlement, sans donnée comptable, avec un état lu (`lue_le`). Plus
  d'e-mail : c'est au gestionnaire de brancher e-mail ou SMS. Lancé par
  `axelcompta/notifier.py` via `axelcompta/taches.py`. Table
  `notifications_envoyees`.
- `synchro.py` (**fait, 2026-09-22**) : synchronisation d'un dossier réel
  (lot du fournisseur, archive brute, catégorisation, écritures, curseur).
  Idempotente, ledger append-only. Une transaction modifiée ou supprimée
  après comptabilisation est contre-passée (`ledger/contrepassation.py`,
  une seule fois) et signalée en quarantaine ; le nouveau montant n'est
  pas rejoué (2026-09-24).
  Politique d'acceptation automatique provisoire (règle ≥ 0,75, ML ≥ 0,90,
  sinon compte 471). Lancée par `axelcompta/synchro_digifactory.py`.
- `revue.py` — `resoudre_ecriture_a_trancher()`, `CategorieInconnueError`
  (**fait, 2026-09-07**) : reclasse une écriture « à trancher » vers le
  compte réel de la catégorie choisie par l'humain — 455 (SASU/EURL) pour
  « usage_personnel » (doc 06 §3.6), n'importe quel autre compte du pack
  sinon. Montants et sens inchangés : une reclassification, pas un nouveau
  calcul.
- **2026-11-05** : le chauffeur peut corriger une décision (nouvelle
  décision, la première reste en base) et annuler pendant 6 secondes
  (PR #81, #82). La notification se marque lue à l'ouverture (AXE-691).
- **V1 (doc 12, phase 3)** : actif, prestataire de signature tranché
  (AXE-441), contre-passations des décisions humaines (AXE-420) et depuis
  la quarantaine (AXE-424), envoi des rappels hors de l'application
  (AXE-808).

## Doc de référence

[doc 05 §5](../../../docs/05-pipeline-categorisation.md#5-étage-4--revue-humaine),
[ADR-004](../../../docs/adr/ADR-004-signature-electronique.md).

## Opérations déjà classées (AXE-823)

`classees.py` (pur) dit, pour chaque écriture classée, qui l'a classée
(`auto` : règle ou modèle, `chauffeur` : décision, `expert` : imputation),
avec quelle confiance et sur quel compte ; filtres, tri par confiance
croissante, compteurs. `verdicts.py` / `verdicts_postgres.py` gardent les
verdicts « juste » / « faux » (migration `b3d8f1a6c924`, append-only),
sans écriture : ils servent à mesurer la précision (AXE-816). Route
`GET /expert/classees`, filtrée et paginée (50) côté serveur.

