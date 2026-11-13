# ingestion/providers/

Le pattern `DataProvider` : toute source de données d'entrée (banque,
plateforme gig) implémente la même interface abstraite. La configuration du
dossier détermine quels providers sont actifs — **le code métier en aval ne
connaît jamais le provider concret**.

**Dépendances :** `core`, `tenants` (config dossier).

## Providers V1

- `DigifactoryProvider` — transactions bancaires (agrège Bridge par contact).
- `RolleeProvider` — settlements plateformes gig (Uber, Bolt…). Depuis
  AXE-818 : `RolleeHttpClient` (API utilisateur, JWT renouvelé, backoff sur
  429/5xx) et `lire_revenus` (une période de revenus → un
  `PlatformSettlement`, ou un rejet avec sa raison si brut − frais ≠ versé).
  Sans client, la fixture du golden test, comme avant.
- `FileImportProvider` — CSV/XLSX/ODS.
- `BridgeProvider` direct — piste parallèle non bloquante, pas de
  développement actif tant que Digifactory couvre le besoin.

## Les trois chemins pour la démo (doc 17 §4-5)

Le token Digifactory est en 401 à ce jour (doc 16 §7) et l'accès sandbox
Rollee n'a pas encore été testé — la démo doit donc pouvoir tourner sans
dépendre d'aucune des deux API externes le jour J :

| Chemin | Provider bancaire | Provider settlement |
|---|---|---|
| A (réel) | `DigifactoryProvider` si déblocage token | `RolleeProvider` si accès sandbox obtenu |
| B (fixtures) | `DigifactoryProvider` contre fixtures (schéma doc 16 §3-4) | `PlatformSettlement` fixtures calées main sur les mêmes transactions (doc 13 §4.1) |
| C (filet, banque seulement) | `FileImportProvider` rejouant `_AUDIT_DONNEES/resultats/fec_ml_taxonomie.csv` (36 152 lignes réelles labellisées ; le chiffre de 48 042 du doc 17 §4bis est daté d'avant une passe de réduction du bucket non catégorisé) | — |

Les trois passent par la même interface — zéro changement ailleurs dans le
pipeline selon le chemin retenu le jour de la démo.

## Statuts

- **Démo (doc 17 semaine 0-1, fait)** : les 5 providers rendent des données
  (fixtures ou fichier réel), plus aucun stub `NotImplementedError` :
  - `FixtureProvider`/`FixtureSettlementProvider` : golden test doc 17 §7.
  - `FileImportProvider` (chemin C) : rejoue le vrai CSV audit, regroupe et
    somme les lignes composites (`piece_ref` type `PAI-185#0`/`#1`...),
    inverse la convention débit-crédit FEC vers le sens relevé bancaire —
    testé contre les 36 152 lignes réelles (229 transactions reconstruites
    sur un dossier test).
  - `DigifactoryProvider` (chemin B) : parsing conforme au schéma doc 16 §3-4
    contre une fixture figée — filtre `deleted`/`future`, déduplique par
    `id` (garde l'`updated_at` le plus récent). Le jour du déblocage token,
    seule la récupération du payload change, pas le parsing.
  - `RolleeProvider` (chemin B) : fixture calée sur le golden test doc 17 §7,
    filtrée par fenêtre de `payout_date`.
  - `NormalizedTransaction` porte désormais un `id` stable (doc 16 §5,
    ajouté semaine 2) : `id` natif du fournisseur pour Digifactory, dérivé
    de dossier+piece_ref+date pour FileImportProvider — nécessaire pour
    relier une transaction à sa `ProposedEntry` (`categorize/`).
  - **Chemin A (réel) non tenté** : token Digifactory toujours en 401
    (doc 16 §7), accès sandbox Rollee toujours non vérifié (doc 17 §5).
- **Au 2026-11-13** : Digifactory réel (depuis septembre, un client par
  branchement depuis AXE-872). `RolleeHttpClient` (AXE-818) : API
  utilisateur, JWT renouvelé sur 401 et rendu à l'appelant pour qu'il le
  garde, 429 et 5xx réessayés ; `lire_revenus` traduit une période en
  `PlatformSettlement` sans jamais arrondir. Depuis AXE-911 : `/users`
  paginé, profil et coordonnées bancaires, en GET seulement. Testé sur des
  réponses construites d'après la documentation ; test de contrat sandbox
  hors CI (`pytest -m rollee`). Sans client, `RolleeProvider()` rend
  toujours la fixture du golden test.
- **V1 (doc 12, phase 0.3 + 1)** : spikes Digifactory/Bridge/Rollee menés à
  terme (accès réel obtenu, pas seulement les fixtures), tous les chemins de
  secours consolidés.

## Doc de référence

[doc 03 §3](../../../../docs/03-architecture.md#3--découpage-en-modules-monolithe-modulaire) (pattern DataProvider),
[doc 13](../../../../docs/13-integrations-plateformes.md) (détail complet du pattern + Rollee),
[doc 16](../../../../docs/16-integration-digifactory.md) (Digifactory),
[doc 17 §4-5](../../../../docs/archive/17-plan-demo-journal-2026-09.md#4-filet-de-sécurité--ingestion-bancaire-digifactorybridge).
