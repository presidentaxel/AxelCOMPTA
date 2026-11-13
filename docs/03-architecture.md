# 03 — Architecture technique

> **État au 2026-11-13** (ajouté ; le reste du doc décrit la cible) :
> - Modules ajoutés au découpage : `pseudonymize/` (seule porte vers un LLM)
>   et `jobs/` (file Postgres, ADR-002). Carte à jour dans le
>   [doc 18](18-organisation-code.md).
> - Point d'entrée HTTP : `axelcompta.api.app`. Les routes vivent dans
>   `api/routes.py`, les jetons dans `api/auth.py` (AXE-840). Les
>   erreurs métier répondent 4xx avec leur phrase, par un seul gestionnaire
>   (`api/erreurs.py`, AXE-839). L'API refuse de démarrer sur une base dont
>   la migration Alembic est en retard (AXE-841).
> - Rôles en place : lecture, membre, admin, `expert_comptable` (habilité
>   par un admin, engagement de responsabilité, AXE-800), et `retire` pour
>   un membre retiré. Un compte de test en lecture seule ouvre l'espace
>   chauffeur de tout dossier du portefeuille (AXE-822).
> - MFA native de Supabase demandée à l'admin et à l'expert-comptable
>   (jeton `aal2`, AXE-812). Le TOTP maison (`tenants/mfa.py`) est retiré.
> - Un worker (`axelcompta.worker`) exécute la file de jobs Postgres :
>   import des dossiers, « Synchroniser », rappels, événements Rollee
>   (AXE-809, AXE-845, AXE-808, AXE-820).
> - Intégrations externes en **branchements** par portefeuille, plusieurs
>   par type, identifiants chiffrés (AXE-872) : mail, SMS, Digifactory,
>   Rollee. Seule route publique sans compte : `POST /webhooks/rollee/{id}`,
>   signée, qui ne lit qu'une fonction `SECURITY DEFINER` (AXE-820).
> - Services externes appelés depuis le 10/11 : Rollee, INSEE et RNE
>   (AXE-849), un bucket S3 privé pour le modèle (AXE-847), l'API Batch
>   d'Anthropic (AXE-887, éteinte par défaut).
> - Depuis le 2026-11-05, la base Supabase `AxelCompta` est la base réelle
>   du portefeuille Serenity ; aucun dossier ni compte de démo n'y reste
>   (doc 17). Isolation stricte (AXE-810), hébergement de production à
>   trancher (AXE-811).

> Statut : brouillon à valider — Dernière mise à jour : 2026-09-24

## 1. Principes directeurs

Calibrés pour une équipe de 1-2 devs visant une fiabilité « comptable » :

1. **Monolithe modulaire, pas de microservices.** Un seul déploiement backend, mais
   des modules internes aux frontières strictes (imports contrôlés, interfaces
   explicites). Les microservices se justifieront peut-être un jour ; à 2 devs ils
   sont un piège opérationnel.
2. **Le cœur comptable est déterministe et pur.** Aucune I/O, aucun appel réseau,
   aucune dépendance ML dans le module `ledger`. Entrées → sorties reproductibles.
   C'est ce qui rend le système testable façon « NASA » (doc 08).
3. **Le ML et les LLM sont à la périphérie, jamais au centre.** Ils *proposent*,
   le cœur *dispose*. Une panne d'OpenAI ne doit jamais empêcher de clôturer un
   exercice.
4. **Event-sourcing léger sur les faits comptables.** Les écritures sont immuables
   (append-only) ; les corrections sont des contre-passations. La piste d'audit est
   un sous-produit gratuit de ce choix. **En code depuis le 2026-09-24**
   (doc 06 I2) : trigger Postgres sur les écritures, les décisions et les
   signatures ; contre-passation d'une transaction bancaire déjà
   comptabilisée que Digifactory modifie ou supprime.
5. **Multi-tenant dès le jour 1.** Isolation par `tenant_id` partout, vérifiée par
   des tests et par Row Level Security en base.
6. **Un tenant = un portefeuille de 1 à N dossiers.** Le mode « gestionnaire »
   (notre pilote : ~200 dossiers) et le mode « mono-entreprise » (futur : 1 dossier)
   sont le **même modèle de données et le même moteur**. **Précisé le
   2026-09-11 (doc 19 §2/§7)** : ce n'est plus qu'une différence d'UI —
   c'est aussi une différence d'**accès** (l'indiv, propriétaire d'un
   dossier, et le gestionnaire, propriétaire d'un tenant, ne voient jamais
   l'un ce qui appartient à l'autre). Le mono n'est pas un troisième cas :
   c'est simplement un compte où les deux liens (`dossier_id` et
   `tenant_id`, §7) pointent vers la même personne. Aucune table, aucun
   service ne suppose N > 1 ni N = 1.
7. **Le comportement métier est de la configuration, pas du code.** Statut
   juridique et régime fiscal sont des attributs du dossier ; taxonomies, règles,
   templates d'écritures sont des **packs métier** versionnés en données (§3bis).
   Ajouter un statut ou un secteur ne crée pas de branche dans le code.
8. **Tout fichier reçu est conservé tel quel** (immutable, horodaté, hashé) avant
   tout parsing. On peut toujours rejouer un import.

## 2. Stack retenue

| Couche | Choix | Justification |
|--------|-------|---------------|
| Backend API | **Python 3.12+ / FastAPI** | Écosystème ML/OCR, typage fort (mypy strict), async pour les I/O Bridge. |
| Validation | **Pydantic v2** | Contrats de données stricts à toutes les frontières. |
| ORM / migrations | **SQLAlchemy 2 + Alembic** | Standard, migrations versionnées et révisables. |
| Base de données | **PostgreSQL 16** | Transactions ACID (non négociable en compta), RLS pour le multi-tenant, JSONB pour les payloads bruts. |
| File d'attente / jobs | **PostgreSQL (SKIP LOCKED) ou Redis + RQ** | Commencer simple : une table de jobs en Postgres suffit largement à 200 dossiers. |
| Stockage objets | **S3-compatible (OVH Object Storage / DO Spaces)** | Justificatifs, exports, datasets. Versioning + verrouillage WORM pour l'archivage légal. |
| ML | **scikit-learn (+ XGBoost/LightGBM)** | Tabulaire + texte court = gradient boosting et TF-IDF font très bien le travail. Pas de deep learning tant que pas nécessaire (doc 07). |
| OCR / Vision | Voir doc 04 §4 | Hybride : extraction native PDF → OCR open-source → Vision LLM en fallback. |
| LLM | **Abstraction `LLMProvider`** (Claude / Gemini / OpenAI interchangeables) | Pas de couplage à un fournisseur ; pseudonymisation en amont (doc 10). |
| Frontend | **TypeScript / React / Next.js** | SSR pour les pages de signature publiques, app riche pour le back-office. |
| UI kit | Voir doc 11 | Design system maison léger sur base Radix/shadcn. |
| Infra | **OVH ou DigitalOcean** — décision en phase 1 | Critères §8. Docker Compose au début, pas de Kubernetes. |
| CI/CD | **GitHub Actions** | Lint, typecheck, tests, conformité FEC, build, déploiement. |
| Observabilité | **Sentry + logs structurés JSON + métriques Prometheus** | Erreurs, latence pipeline, taux de catégorisation en continu. |

## 3. Découpage en modules (monolithe modulaire)

```text
axelcompta/
├── core/            # Types partagés, Result, erreurs, monnaie (int centimes), dates
├── tenants/         # Tenants (mode portefeuille ou mono), dossiers, statuts/régimes
├── packs/           # Packs métier : taxonomies, règles système, templates, config plateformes
├── ingestion/       # Orchestration de l'ingestion ; sous-modules :
│   └── providers/   #   DataProvider ABC + implémentations (Digifactory, Rollee, FileImport ; Bridge direct en piste parallèle — doc 16 §8)
├── documents/       # Justificatifs : stockage, OCR, Factur-X, matching transactions
├── categorize/      # Pipeline hybride : règles → ML → LLM → revue humaine
├── anomaly/         # Détection d'abus / anomalies, scoring, alertes
├── ledger/          # ❤️ Moteur comptable PUR : écritures, journaux, balance, immos, TVA
├── closing/         # Clôture d'exercice, états financiers, liasse (modèle pivot)
├── filings/         # Renderers : FEC, PDF, EDI-TDFC, dossier INPI
├── workflow/        # Validation, circuit de relecture, signature électronique
├── api/             # Routes FastAPI, auth, permissions (aucune logique métier)
└── ml/              # Entraînement, évaluation, registry de modèles (hors runtime API)
```

**Pattern DataProvider (ingestion/providers/) :** toute source de données d'entrée implémente l'interface `DataProvider`. La configuration du tenant détermine quels providers sont actifs — le code métier ne connaît pas le provider. Providers V1 : `DigifactoryProvider` (transactions bancaires, agrège Bridge par contact — doc 16), `RolleeProvider` (settlements plateformes gig), `FileImportProvider` (CSV/XLSX/ODS). Un `BridgeProvider` direct est une piste parallèle non bloquante, à tester en sandbox après le pilote Digifactory (doc 16 §8) — pas de développement actif tant que Digifactory couvre le besoin. Détails : doc 13.

**Règles de dépendance** (vérifiées par import-linter en CI) :

- `ledger` ne dépend de rien sauf `core`. Jamais de `categorize`, `ml`, `api`.
- `categorize` produit des `ProposedEntry`, seul `workflow` peut les transformer en
  écritures via `ledger` après validation.
- `api` n'importe que les façades publiques de chaque module (`module/service.py`).
- Personne n'importe `ml` au runtime : les modèles sont chargés comme artefacts.

## 3bis. Les deux axes de configuration : statut du dossier × pack métier

Chaque **dossier** est indépendant et porte sa configuration complète en propre —
le tenant ne fournit que des valeurs de pré-remplissage à la création, jamais
d'héritage implicite (doc 06 §7). Deux configurations orthogonales, lues par tout
le système :

1. **Profil juridique et fiscal** (`statut`) : forme (SASU, SAS, EURL, SARL, EI),
   régime d'imposition (IS, option IR bornée à 5 exercices, IR sans limite pour
   l'EURL, la SARL de famille et l'EI, micro), régime TVA (réel normal, réel
   simplifié en lecture avant 2027, franchise),
   obligations de dépôt. Détermine les formulaires de liasse, le traitement de la
   rémunération du dirigeant, le compte utilisé en cas d'usage personnel (455 vs
   108), le dépôt INPI ou non.
   → Matrice complète et régimes opérationnels V1 : doc 06 §7. Implémentée
   depuis le 2026-09-26 dans `tenants/matrice_statuts.toml` (données) et
   `tenants/statuts.py` (validation, lecture).
2. **Pack métier** (`secteur`) : taxonomie de catégories, règles système, templates
   d'écritures sectoriels, paramètres de détection d'anomalies, adaptation ML.
   Le pack **VTC** est le premier ; un pack est un ensemble de données versionnées
   (+ ses tests), pas du code.

Exemple : deux chauffeurs du même client → même pack `vtc`, mais l'un en
`EURL à l'IR` et l'autre en `SASU IS` produisent des liasses différentes.
Inversement, une SASU de boulangerie partagerait le statut du second avec un autre
pack. **Aucun `if secteur == "vtc"` ni `if forme == "SASU"` hors de ces deux
modules de configuration.**

## 4. Modèle de données (vue logique simplifiée)

```mermaid
erDiagram
    TENANT ||--o{ DOSSIER : possede
    DOSSIER ||--o{ COMPTE_BANCAIRE : suit
    COMPTE_BANCAIRE ||--o{ TRANSACTION : recoit
    TRANSACTION ||--o| JUSTIFICATIF : "matché à"
    TRANSACTION ||--o| PROPOSITION : "catégorisée en"
    PROPOSITION ||--o| ECRITURE : "validée devient"
    DOSSIER ||--o{ ECRITURE : contient
    ECRITURE ||--|{ LIGNE_ECRITURE : "partie double"
    DOSSIER ||--o{ IMMOBILISATION : detient
    IMMOBILISATION ||--o{ DOTATION : genere
    DOSSIER ||--o{ EXERCICE : "découpé en"
    EXERCICE ||--o| LIASSE_PIVOT : produit
    TRANSACTION ||--o{ ALERTE_ANOMALIE : declenche
    DOSSIER ||--o| PROFIL_COMPORTEMENTAL : "habitudes apprises"
```

Points structurants :

- **`TRANSACTION` (fait brut) ≠ `ECRITURE` (fait comptable).** La transaction
  bancaire est conservée brute et immuable ; l'écriture est sa traduction comptable
  validée. Lien 1-n possible (une transaction → écriture composée TTC/HT/TVA).
- **`PROPOSITION`** porte : catégorie proposée, source (`RULE | ML | LLM | HUMAN`),
  score de confiance, features d'explication. Historisée même après validation
  (données d'entraînement futures + audit).
- **Montants en centimes (entiers), jamais en flottants.** Type `Money` dans `core`.
- **`LIASSE_PIVOT`** : représentation interne case-par-case des formulaires (cf.
  doc 02 §5), sérialisée en JSONB, versionnée par millésime fiscal. Les formulaires
  inclus dépendent du statut du dossier (2065+2050-suite en IS, 2031+annexes en IR…).
- **`PROFIL_COMPORTEMENTAL`** : statistiques apprises par dossier (conso carburant
  habituelle, enseignes récurrentes, montants types) recalculées incrémentalement,
  utilisées par `anomaly` (doc 07 §3.3). Ce n'est pas un modèle ML par dossier,
  c'est une fiche de stats — peu coûteux, recalculable à volonté.

## 5. Flux d'une transaction (chemin nominal)

```mermaid
sequenceDiagram
    participant B as Digifactory (Bridge) / Import fichier
    participant I as ingestion
    participant C as categorize
    participant A as anomaly
    participant W as workflow (humain)
    participant L as ledger
    B->>I: transactions brutes
    I->>I: normalisation, déduplication, hash
    I->>C: TransactionNormalisée
    C->>C: 1. règles dures (déterministe)
    C->>C: 2. modèle ML si pas de règle
    C->>C: 3. LLM si confiance < seuil (données pseudonymisées)
    C->>A: transaction + catégorie proposée
    A-->>W: alerte si anomalie (ex. dépense perso suspectée)
    C->>W: PROPOSITION (auto-validable si confiance ≥ seuil et pas d'alerte)
    W->>L: validation → écriture(s) en partie double
    L->>L: invariants : balance équilibrée, séquence, période ouverte
```

Règle d'or : **une proposition à haute confiance issue des règles dures peut être
auto-validée par configuration du tenant ; tout ce qui vient du LLM ou porte une
alerte passe par un humain.**

## 6. Frontières et contrats

Chaque frontière du système a un contrat Pydantic versionné :

| Frontière | Contrat | Notes |
|-----------|---------|-------|
| Digifactory → ingestion | `DigifactoryTransaction` | Payload brut archivé en JSONB avant mapping (doc 16). Même contrat prévu pour un futur `BridgeProvider` direct (doc 16 §8). |
| Fichier → ingestion | `ImportProfile` + `RawRow` | Profil de mapping par client (colonnes, formats de date, séparateurs). |
| ingestion → categorize | `NormalizedTransaction` | Libellé nettoyé, montant signé en centimes, devise, dates, compteur de doublons. |
| categorize → workflow | `CategorizationProposal` | Catégorie, compte PCG cible, confiance ∈ [0,1], source, explication. |
| workflow → ledger | `JournalEntryDraft` | Validé par qui, quand ; le ledger re-vérifie tous les invariants (défense en profondeur). |
| closing → filings | `LiassePivot` | Indépendant du format de sortie. |
| * → LLM | `PseudonymizedPrompt` | Construit uniquement via le module de pseudonymisation (doc 10 §4). |

## 7. Auth, rôles, multi-tenant

> **Réécrit le 2026-09-11** — la version précédente (`admin_tenant`/
> `comptable`/`analyste` côté gestionnaire + `signataire_externe` par lien
> magique sans compte) datait d'avant doc 19 (2026-09-06) et n'avait
> jamais été corrigée depuis : elle décrivait un produit où seul le
> gestionnaire a un vrai compte et le chauffeur signe par lien — l'inverse
> de ce qui est acté depuis (doc 19, précisé le 2026-09-11).

**Un seul type de compte, deux liens indépendants — pas des rôles
exclusifs.** Un compte (Supabase Auth aujourd'hui, ADR-003) peut porter :

- `dossier_id` (optionnel) — accès **indiv** à ce dossier : transactions,
  revue, justificatifs, clôture, signature (doc 19 §5). Jamais l'accès à
  un autre dossier.
- `tenant_id` (optionnel) — accès **gestionnaire** à ce portefeuille :
  agrégats par dossier, statut d'onboarding, invitations (doc 19 §6).
  Jamais le détail d'un dossier, quel qu'il soit.

Les deux liens peuvent coexister **sur le même compte** — c'est le mode
mono (doc 03 §1 principe 6) : `tenant_id` pointe vers le portefeuille d'un
seul dossier, `dossier_id` vers ce même dossier. Pas un troisième type de
compte, pas de champ `role` à trancher en dur — juste deux relations qui
peuvent être vraies indépendamment. Ni compte gestionnaire ni compte indiv
n'a par défaut les deux liens ; les avoir tous les deux est le cas mono,
pas l'inverse.

**Conséquence pratique** (**fait le 2026-09-21**, doc 18) : l'« auth
gestionnaire » (doc 17 §9, jadis « chantier séparé, pas commencé ») n'est
**pas** un système à part —
c'est la vérification de token Supabase déjà construite pour l'indiv
(`api/auth.py`, doc 17 §9 Semaine 3) à laquelle on ajoute la lecture du
lien `tenant_id`. Pas de nouveau mécanisme d'authentification, juste une
donnée en plus dans les métadonnées du compte et des vérifications d'accès
supplémentaires côté API. **Les deux liens sont lus dans `app_metadata`**
(écrit côté serveur, clé service role), jamais dans `user_metadata`, que
l'utilisateur peut modifier lui-même via l'API Auth de Supabase : c'était
la faille du lien `dossier_id`, corrigée le 2026-09-21.

- **Auth** : email + mot de passe via Supabase Auth (ADR-003, exception
  actée pour la V1 aussi, doc 12 §0.1), MFA à évaluer en V1 pour le lien
  `tenant_id` (plus sensible qu'un dossier individuel — accès à
  l'onboarding de tout un portefeuille). SSO (SAML/OIDC) en phase 2 si la
  banque l'exige.
- **Isolation** : `tenant_id`/`dossier_id` obligatoires sur toutes les
  tables métier concernées + RLS PostgreSQL activée + tests d'isolation
  automatisés (doc 09 §6) — l'isolation gestionnaire↔indiv (doc 19 §2.4)
  suit la même logique que l'isolation tenant↔tenant, pas un mécanisme
  différent. **RLS posée pour de vrai le 2026-09-22** (doc 12 §1.1,
  migration `87fc7238e52e`) : un second rôle Postgres (`axelcompta_web`,
  ni propriétaire ni superuser) exécute les requêtes de `api/routes.py`,
  soumis aux policies — `user` (migrations, amorçage des jeux de test,
  `synchro_digifactory`, `notifier`) reste propriétaire, jamais concerné,
  ces scripts traitent volontairement plusieurs dossiers à la fois. Le
  contexte (`app.dossier_id`/`app.tenant_id`) est posé par requête via un
  middleware (`axelcompta/core/rls.py`), `set_config(..., true)` —
  portée transaction, jamais fuité entre deux requêtes qui
  réutiliseraient la même connexion du pool. 7 tests d'isolation
  (`tests/integration/test_rls_isolation.py`) : indiv/gestionnaire, lignes
  d'écriture (isolées via leur écriture parente, pas de `dossier_id`
  propre), et l'écriture d'une décision hors de son propre dossier
  refusée par le `WITH CHECK`, pas seulement la lecture.
- **Signature** : ne passe plus par un lien magique sans compte
  (`signataire_externe`, abandonné le 2026-09-06 avec doc 19) — c'est
  l'indiv authentifié qui signe depuis son propre compte (doc 19 §5.3,
  doc 20 §4bis).

## 8. Choix d'hébergement OVH vs DigitalOcean

| Critère | OVHcloud | DigitalOcean |
|---------|----------|--------------|
| Localisation données (exigence banque) | ✅ France, SecNumCloud possible | ⚠️ UE possible (AMS/FRA) mais société US (CLOUD Act) |
| Postgres managé | ✅ | ✅ |
| Object Storage S3 | ✅ | ✅ (Spaces) |
| Perception par une banque française | ✅ Fort argument | ⚠️ Friction probable |
| DX / simplicité | Moyenne | Très bonne |

**Recommandation** : DigitalOcean acceptable pour les environnements de dev/staging ;
**production chez OVH** (argument commercial décisif face à une banque + CLOUD Act).
Décision à confirmer après le questionnaire sécurité du client.

## 9. Environnements et déploiement

- `dev` (local, Docker Compose : Postgres + MinIO + backend + front).
- `staging` (données synthétiques ou pseudonymisées **uniquement** — jamais de vraies
  données bancaires hors prod).
- `prod` (OVH, sauvegardes Postgres PITR, restauration testée trimestriellement).
- Déploiement : image Docker unique backend + front statique/SSR. Migrations Alembic
  exécutées en étape dédiée avec verrou. Rollback = image précédente + migrations
  down testées.

## 10. Décisions d'architecture à confirmer (ADR à écrire)

Tenir un dossier `docs/adr/` (Architecture Decision Records, 1 page par décision) :

- [ ] ADR-001 : monolithe modulaire (ce document) — à acter.
- [ ] ADR-002 : Postgres comme file de jobs vs Redis — trancher au premier besoin réel.
- [ ] ADR-003 : hébergement prod OVH — après questionnaire sécurité banque.
- [ ] ADR-004 : prestataire signature électronique (Yousign pressenti : français, API propre, eIDAS) .
- [ ] ADR-005 : moteur OCR retenu après benchmark (doc 04 §4).
- [ ] ADR-006 : bibliothèque de génération PDF des liasses (rendu fidèle aux CERFA).
