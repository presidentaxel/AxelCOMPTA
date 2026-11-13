# ingestion/

Orchestration de l'ingestion : sélectionne le(s) `DataProvider` actif(s) pour
un dossier donné (voir [`providers/`](providers/README.md)), déclenche les
appels (sync périodique ou webhook), normalise la sortie brute avant de la
transmettre à `categorize/`.

**Dépendances :** `core`, `tenants`, `packs` (config dossier + pack), `ledger`
(types uniquement, pour construire les `Ecriture` de settlement — `ledger`
ne dépend jamais d'`ingestion` en retour, règle absolue doc 03 §3).

## Fichiers

- `providers/` — pattern `DataProvider` (voir son propre README).
- `reconciliation.py` — `reconcilier()` (doc 13 §4.2, **fait semaine 2**) :
  montant ±1 centime, fenêtre de date [-3j, +5j] autour du `payout_date`,
  libellé contenant le nom de la plateforme. Trois états rapportés (doc 13
  §4.3, réduit) : `RECONCILIE`, `EN_ATTENTE_BANQUE`, `REVUE_MANUELLE` — pas
  de file de revue construite (doc 17 §3), l'état est juste rapporté.
- `settlements_plateforme.py` (AXE-821) — relevés de revenus des
  plateformes gardés une fois par compte et par période, et leur état de
  rapprochement (`en_attente_banque`, `reconcilie`, `a_classer`,
  `a_verifier`). Un relevé déjà ventilé n'est jamais réécrit. Le
  rapprochement et la ventilation sont orchestrés par
  `axelcompta/revenus_rollee.py`.
- `ecritures_settlement.py`, `ecriture_de_ventilation()` (AXE-821) — l'OD
  `{virement}:ventilation-plateforme` qui reprend le net du 706 et pose
  brut HT, TVA et commission. Le virement n'est pas modifié, le 512 ne
  bouge pas, aucune ligne au 471.
- `ecritures_settlement.py` — `construire_ecriture_settlement()` (doc 13 §5,
  **fait semaine 2**) : ventilation TVA réelle depuis un settlement
  réconcilié, templates de données par régime de commission (`france_20`
  Uber, `autoliquidation_ue` Bolt), taux de TVA recettes figé à 10% assujetti
  (profil unique démo, doc 17 §3).

## Journal d'ingestion (fait le 2026-09-22)

- `orm.py` / `journal.py` / `journal_postgres.py` : archive brute
  insert-only (`ingestion_brut`, clé = empreinte du contenu), quarantaine
  idempotente (`quarantaine_ingestion`), curseur de reprise par (dossier,
  source) qui ne recule jamais (`curseurs_synchro`).
- `providers/digifactory.py` : `parser_lot` (une ligne malformée devient un
  rejet sans bloquer le lot), `DigifactoryProvider.lire_lot(dossier,
  curseur)` (appelle `/transactions/{contact_nr}` avec le contact du dossier,
  refuse un dossier sans contact). L'orchestration vit dans
  `workflow/synchro.py`, pas ici (graphe de dépendances, doc 18).
- `consentement.py` / `consentement_postgres.py` (**fait, 2026-09-24**,
  doc 14 §2.2) : classe le consentement DSP2
  (`actif` / `a_renouveler` à 14 jours / `expire` / `jamais_connecte`)
  et enregistre l'état courant (`consentements_bancaires`). Pas d'e-mail,
  pas d'écran. Relevé par `synchro_digifactory.py` ; un échec de lecture
  des comptes ne fait pas échouer la synchro des transactions.
  **2026-09-25** : la même ligne porte la santé de connexion
  (`relever_sante` : auth à refaire, sans accès, en pause, ok). Le premier
  chargement des transactions est découpé par mois (`fenetres_mensuelles`) ;
  une réponse vide est un lot vide, pas un échec.

## Contenu prévu (au-delà de la démo)

- Normalisation `Decimal` → centimes à l'ingestion (fait dans les providers
  eux-mêmes pour la démo — semaine 2 : à centraliser ici en V1).
- Filtrage des transactions `deleted`/`future` côté banque (doc 16 §5, fait
  pour `DigifactoryProvider`).
- File de jobs (Postgres SKIP LOCKED au départ, doc 03 §2).

## Comptes bancaires (AXE-832)

- `comptes_bancaires.py` : registre des comptes bancaires d'un dossier et de
  leur sous-compte de banque (5121, 5122… dans l'ordre d'apparition, jamais
  renuméroté). `compte_de()` donne le sous-compte d'une opération à partir
  de son `compte_bancaire` (Digifactory : `account_id`) ; banque inconnue :
  512. `comptes_releves()` lit `GET /accounts` (nom, solde).
- `comptes_bancaires_postgres.py` : table `comptes_bancaires` (migration
  `c3f7a2e81d45`, RLS par dossier, rôle web en lecture seule).
- `journal.comptes_des_transactions()` relit l'`account_id` de chaque
  transaction archivée, pour la reprise des écritures restées au 512.
- `a_choisir()` (AXE-851) : par dossier, les comptes « à décider »
  (AXE-729), depuis quand, et combien d'opérations archivées ils retiennent.
  En Postgres, une fonction `SECURITY DEFINER`
  (`axelcompta_comptes_a_choisir`, migration `a7d3e5c1b904`) ne renvoie que
  ces comptages : le rôle web ne lit pas l'archive brute. Elle applique la
  règle de `dossiers_isolation` elle-même ; sans contexte RLS, elle ne voit
  rien. Le gestionnaire le voit dans Entreprises, le dirigeant dans sa
  cloche (`notifications.TYPE_COMPTES_A_CHOISIR`).

## Statuts

- **Démo (doc 17 semaines 0-2, fait)** : réconciliation réelle + génération
  d'écriture avec ventilation TVA réelle (golden test doc 13 §5.3 reproduit
  exactement, cas Bolt autoliquidation testé séparément).
- **V1 (doc 12, phase 1)** : retries, monitoring des flux par dossier,
  planificateur (file de jobs, ADR-002), normalisation centralisée.
  Orchestration multi-dossiers : **faite le 2026-09-22** en lancement manuel
  (`python -m axelcompta.synchro_digifactory`), lancée toutes les heures
  par le cron `axelcompta.taches`.
- **Fait du 2026-11-05 au 2026-11-09** : contacts importés sur liste
  (AXE-726), dossiers pilotes réels (AXE-727), comptes bancaires retenus
  (AXE-729, AXE-851), sous-comptes 512x (AXE-832), type d'opération et
  catégorie de la banque portés par la transaction (AXE-826), nouveaux
  contacts proposés (AXE-845).
- **Fait du 2026-11-12 au 2026-11-13 (Rollee)** :
  - `comptes_rollee.py` : le user Rollee d'un dossier et ses comptes de
    plateformes (connecté, à reconnecter), sans montant (AXE-819) ;
  - `webhooks_rollee.py` : événements reçus, gardés une fois par empreinte
    du corps (AXE-820) ;
  - `settlements_plateforme.py` : relevés par période et leur état,
    `a_verifier()` pour « À traiter », `delie` quand le lien est retiré
    (AXE-821, AXE-891, AXE-911) ;
  - `rapprochement_rollee.py` (pur) : relier un user Rollee au bon dossier
    par empreintes HMAC ; `liens_rollee.py` : l'origine du lien,
    l'historique des liens retirés et la file « à choisir » (AXE-911).
  Chacun a son dépôt `_postgres.py`. `digifactory_contacts.py` (ex
  `demo_digifactory.py`, AXE-840) : le contact Digifactory → dossier.
- **Prévu au 2026-11-13** : première synchro des chauffeurs réels
  (AXE-728), relevés Uber et Bolt en secours de Rollee (AXE-801), sortie
  de « à vérifier » (AXE-912), mois d'avant la connexion Digifactory
  (AXE-833).

## Doc de référence

[doc 04 §5](../../../docs/04-ingestion-donnees.md#5-normalisation--la-sortie-unique-du-module),
[doc 16 §5](../../../docs/16-integration-digifactory.md).
