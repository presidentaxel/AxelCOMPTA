# ADR-003 — Hébergement et base de données

**Date :** 2026-06-16 — Mise à jour : 2026-09-24
**Statut :** partiellement accepté — base de données et auth tranchées (Supabase, y compris pour la V1, voir mise à jour 2026-09-08), compute à décider quand le code est stable

> **État au 2026-11-05** : le projet Supabase `AxelCompta` (eu-west-1)
> devient la base de production du portefeuille Serenity (doc 17) ; le
> menu Démo et toutes les données de démo sont retirés.
> Isolation stricte de la production : AXE-810. Décision de
> production (région, sauvegardes, CLOUD Act pour l'auth) et restauration
> chronométrée : AXE-811.
**Décideurs :** Louis Vedovato

## Contexte

AxeLCompta traite des données bancaires et fiscales de personnes morales françaises. Le client pilote est dans le secteur parabancaire (gestionnaire de chauffeurs VTC). Ce type de client soumet généralement un questionnaire sécurité fournisseur avec des exigences sur la localisation des données et la souveraineté.

---

## Décision 1 — Base de données : Supabase ✅ (retenu)

**Supabase est le choix retenu pour la base de données** (dev, staging et prod jusqu'à preuve du contraire).

> **Mise à jour 2026-09-24 — appliqué pour de vrai.** Jusqu'ici seule
> l'auth tournait sur Supabase : la base applicative était restée sur un
> Postgres docker local (décision du 2026-09-07, doc 17 §9 bloc B), en
> contradiction avec cette décision. Louis tranche : la base de dev et de
> démo passe sur le projet Supabase `AxelCompta-demo` (eu-west-1). Rien ne
> change dans le code applicatif (connection string standard, Alembic, RLS
> maison). Ajustements : connexion par le Session pooler (la connexion
> directe est en IPv6 seulement), mot de passe du rôle `axelcompta_web`
> fourni par `AXELCOMPTA_WEB_PASSWORD` au lieu d'être versionné, et tests
> d'intégration verrouillés sur un Postgres local (ils suppriment toutes
> les tables). Data API (PostgREST) toujours désactivée sur le projet.

Supabase = PostgreSQL managé avec tooling (dashboard SQL, RLS visuel, backups, PITR). Tout ce qui est prévu dans l'architecture (SQLAlchemy, Alembic, RLS multi-tenant) fonctionne sans modification — c'est une connection string PostgreSQL standard.

| Critère | Supabase | Scaleway Managed PG |
|---------|----------|-------------------|
| Prix | **$25/mois** (Pro) | ~€50/mois |
| PITR | ✅ 7 jours inclus | ✅ inclus |
| RLS | ✅ first-class | Manuel |
| Dashboard SQL | ✅ excellent | pgAdmin manuel |
| Société | 🇺🇸 US (données Frankfurt 🇩🇪) | 🇫🇷 France |
| CLOUD Act | ⚠️ applicable | ✅ non applicable |

### Risque CLOUD Act

Supabase est une société américaine. Le CLOUD Act permet aux autorités US d'accéder aux données d'une société US même hébergées en EU. Ce risque est **accepté provisoirement** avec un déclencheur clair pour le réexaminer.

### Plan de migration si nécessaire

La migration de Supabase vers n'importe quel PostgreSQL managé (Scaleway, OVHcloud) se résume à :

1. `pg_dump` depuis Supabase → `pg_restore` sur la cible
2. Changer `DATABASE_URL` dans les variables d'environnement
3. Rejouer `alembic upgrade head` sur la cible pour vérifier la cohérence
4. Basculer le DNS / la config applicative

**Durée estimée : ½ journée.** Ce n'est pas une refonte — à condition de ne jamais utiliser de fonctionnalités propriétaires Supabase (PostgREST auto-généré, Supabase Auth, Supabase Storage). Règle : **n'utiliser que la connection string PostgreSQL standard**. Tout passe par SQLAlchemy et Alembic.

### Déclencheur de réexamen

Migrer vers Scaleway ou OVHcloud Managed PostgreSQL si **le questionnaire sécurité d'un client exclut explicitement les prestataires soumis au CLOUD Act.** Pas avant.

---

## Décision 2 — Compute / infra applicative : à trancher plus tard

La décision sur le compute (VMs, containers, PaaS) est reportée à quand le code est suffisamment avancé pour connaître les contraintes réelles (taille des images Docker, besoins mémoire pour les modèles ML, fréquence des jobs).

### Options retenues pour évaluation

| Option | Avantage principal | Inconvénient |
|--------|-------------------|-------------|
| **Scaleway** (Containers ou Instances) | Société française, bon équilibre DX/contrôle | Plus d'ops que PaaS |
| **OVHcloud** (Public Cloud) | Argument fort face aux banques, SecNumCloud possible | DX plus rugueuse |
| **Clever Cloud** | Zéro ops, PaaS français | Moins adapté aux workers ML longue durée |

### Déclencheur de décision

Trancher quand : premier déploiement staging réel avec données synthétiques (Phase 1, tâche 1.1). La contrainte de localisation France reste non négociable pour la production.

---

## Règle transverse : aucun lock-in propriétaire

Quelle que soit la décision finale sur le compute :
- **Base de données** : SQLAlchemy + Alembic uniquement, jamais le client JS Supabase ou PostgREST
- **Stockage fichiers** : SDK S3 standard (`boto3`), jamais le SDK Supabase Storage
- **Auth** : implémentation maison (FastAPI + JWT), jamais Supabase Auth

Ces trois règles garantissent que changer de provider = changer des variables d'environnement, pas réécrire du code.

**Mise à jour 2026-09-08 — Supabase Auth passe d'exception démo à décision
assumée (Louis) :** l'entorse ouverte le 2026-09-07 pour la démo est
maintenue au-delà, y compris pour la V1. Différence avec la règle
transverse ci-dessus, actée en connaissance de cause plutôt que révertée :

- **Le coût de migration n'est pas symétrique avec celui de la base.** La
  migration base (ligne 32-38 ci-dessus) est un `pg_dump`/`pg_restore` d'une
  demi-journée parce qu'on n'utilise que la connection string standard.
  Migrer hors de Supabase Auth plus tard (schéma `auth`/GoTrue, sessions,
  flux d'invitation `service_role`) demanderait de réécrire l'auth
  applicative elle-même, pas de rejouer une migration — ce n'est pas la
  même classe de coût, et ADR-003 doit le dire explicitement plutôt que
  laisser le lecteur croire que « connection string standard » couvre
  aussi l'auth.
- **Le déclencheur de réexamen de la base (ligne 45) doit donc couvrir
  l'auth aussi, pas seulement la base** : si le questionnaire sécurité d'un
  client exclut les prestataires soumis au CLOUD Act, la bascule concerne
  Supabase dans son ensemble (base **et** auth) — pas la base seule suivie
  d'un auth qui resterait en place faute d'avoir été listé. L'auth porte en
  plus des données d'identité (email, éventuellement téléphone) des
  chauffeurs, pas seulement des données bancaires/fiscales.
- Reste inchangé : stockage fichiers toujours via SDK S3 standard, jamais
  Supabase Storage.

Décision : accepté, pas un pense-bête « à corriger avant V1 » — mais le
risque CLOUD Act qui s'appliquait déjà à la base s'étend maintenant à
l'identité des utilisateurs, et le jour où ce risque se matérialise
(déclencheur ci-dessus), la facture de sortie sera plus lourde côté auth que
côté base. À rouvrir cet ADR si ce compromis change.
