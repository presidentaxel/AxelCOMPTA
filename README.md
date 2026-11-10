# AxeLCompta — Documentation de cadrage

Plateforme B2B de production comptable automatisée : ingestion bancaire (Bridge,
fichiers), catégorisation hybride (règles → ML → LLM), détection d'anomalies,
moteur comptable PCG, liasses, signature électronique, trajectoire vers la
télédéclaration en Partenaire EDI habilité.

**Générique par construction** : deux modes d'usage (un gestionnaire qui gère N
dossiers — notre pilote avec ~200 chauffeurs — ou une entreprise qui gère sa propre
compta), statut juridique et régime fiscal configurés **par dossier** (EURL ici,
SASU là, micro demain), et des « packs métier » par secteur dont le VTC n'est que
le premier.

**Où lire l'état du projet :** dans le repo, un seul endroit, le
[doc 12](docs/12-roadmap-todo.md) (fait, en cours, prévu ; à jour au
2026-11-10). Le suivi au jour le jour est dans Linear, projet
[Axel Compta — V1 prod](https://linear.app/axel-project/project/axel-compta-v1-prod-api-ingestion-fiabilite-899778ce7b41),
cible le 31/12/2026. Le passage en
mode réel est dans le [doc 17](docs/17-plan-demo-backend.md), la carte du code le
[doc 18](docs/18-organisation-code.md). L'historique daté (journaux de
sprint, notes de session) est dans [docs/archive](docs/archive/) et ne se
met plus à jour.

## Sommaire

| Doc | Contenu | À lire pour |
|-----|---------|-------------|
| [DESIGN.md](DESIGN.md) | **Design system complet** : tokens couleur, typo, spacing, composants, breakpoints, Do's & Don'ts | Avant tout travail front — référence d'implémentation |
| [01 — Objectifs produit](docs/01-objectifs-produit.md) | Vision, périmètre, non-objectifs, personas, KPIs, risques | Tout le monde, en premier |
| [02 — Cadre réglementaire](docs/02-cadre-reglementaire.md) | Monopole expertise comptable (Cass. com. 17/09/2025), DSP2, FEC, stratégie Partenaire EDI en 3 temps, INPI, facturation électronique, RGPD juridique | Décisions business et juridiques |
| [03 — Architecture](docs/03-architecture.md) | Monolithe modulaire, stack Python/FastAPI + TS/Next, modèle de données, multi-tenant, configuration statut × pack métier, hébergement | Les devs, avant tout code |
| [04 — Ingestion](docs/04-ingestion-donnees.md) | Bridge, profils d'import CSV/Excel/ODS, OCR/Vision en cascade, matching justificatifs | Devs + compréhension du « pas de ticket ≠ blocage » |
| [05 — Pipeline de catégorisation](docs/05-pipeline-categorisation.md) | 4 étages règles→ML→LLM→humain, profil comportemental par dossier, détection d'abus, explicabilité | Le cœur « intelligent » du produit |
| [06 — Moteur comptable](docs/06-moteur-comptable.md) | Invariants, templates d'écritures (pack VTC : carburant, véhicule, LOA, amortissements), clôture, liasse pivot, **matrice multi-statuts** | À relire avec un expert-comptable |
| [07 — ML & données](docs/07-ml-donnees-entrainement.md) | Audit du dataset 10 ans, features, modèles, évaluation, hiérarchie global→client→dossier, MLOps | Avant tout entraînement |
| [08 — Qualité de code](docs/08-qualite-code.md) | Règles NASA « Power of Ten » transposées, conventions, CI bloquante, doctrine d'erreurs | Les devs, en continu |
| [09 — Stratégie de tests](docs/09-strategie-tests.md) | Propriétés, golden tests FEC/liasses, intégration, isolation multi-tenant, charge, validation comptable humaine | Les devs, en continu |
| [10 — Sécurité & RGPD](docs/10-securite-rgpd.md) | Modèle de menace, chiffrement, pseudonymisation avant LLM, cycle de vie des données, incident | Avant le pilote |
| [11 — UX/UI](docs/11-ux-ui.md) | Principes UX, UI adaptative (1 vs 200 dossiers, statut du dossier), les 3 écrans clés | Avant les maquettes — lire DESIGN.md en parallèle |
| [12 — Roadmap & TODO](docs/12-roadmap-todo.md) | Phases 0→5, TODO maître détaillée, critères de sortie, règles de pilotage | Le plan d'exécution |
| [13 — Intégrations plateformes](docs/13-integrations-plateformes.md) | Pattern DataProvider, Rollee (fleet mode), réconciliation settlements, TVA transport 10%, templates Uber/Bolt | Avant tout code d'ingestion ou de catégorisation VTC |
| [14 — Onboarding / Offboarding](docs/14-onboarding-offboarding.md) | Cycle de vie d'un tenant : collecte des données, import en masse, connexion providers, reprise historique, export et purge | Avant le pilote client (phase 4) et à la signature de tout nouveau client |
| [15 — Observabilité](docs/15-observabilite.md) | Métriques métier (KPIs taux catégorisation, coût LLM, balance, FEC), métriques techniques (mémoire ML, file de jobs, Bridge/Rollee), logs structurés JSON, alerting, dashboards Grafana | Avant le premier déploiement staging |
| [16 — Intégration Digifactory](docs/16-integration-digifactory.md) | Connecteur Digifactory (agrégateur Bridge), schéma fixtures, statut du blocage token (401) | Avant tout code d'ingestion bancaire |
| [17 — Mode réel](docs/17-plan-demo-backend.md) | Passage en mode réel (05/11), données de démo retirées, import des chauffeurs Digifactory | Avant de lancer l'app ou de toucher aux données |
| [18 — Organisation du code](docs/18-organisation-code.md) | Carte de l'arborescence `backend/`/`frontend/` vers les modules du doc 03, graphe de dépendances | Avant de toucher au code, pour situer un module |
| [19 — Parcours utilisateur](docs/19-parcours-utilisateur.md) | Compte chauffeur (mobile) relié à sa propre banque, onboarding et visibilité gestionnaire, deux modes de connexion bancaire par dossier, mono-compte | Avant tout code front — complète doc 11 et doc 14 |
| [20 — Dépôt des comptes annuels (INPI)](docs/20-integration-inpi-depot-comptes.md) | Schéma de l'API de dépôt Guichet Unique, pièces jointes, signature qualifiée RGS obligatoire (recoupe ADR-004) | Avant tout code de génération du dossier greffe/INPI |
| [ADR 001-007](docs/adr/) | Architecture Decision Records : monolithe, file de jobs, hébergement, signature, OCR, PDF liasses, modèle ML de catégorisation | À lire avant de remettre en question une décision d'architecture |
| [Archive](docs/archive/) | Journaux de sprint, notes de session, référence Revolut | Pour retrouver pourquoi une chose a été faite |

## Les 7 décisions structurantes déjà prises (à confirmer)

1. **Positionnement éditeur de logiciel** : l'utilisateur professionnel valide tout,
   AxeL ne tient pas la comptabilité en son nom (doc 02 §2.3).
2. **Monolithe modulaire** avec cœur comptable pur et déterministe, ML/LLM en
   périphérie (doc 03 §1).
3. **Liasse pivot** indépendante du format de sortie → la télédéclaration EDI est
   un renderer qu'on branche plus tard, pas une refonte (doc 02 §5, doc 06 §6).
4. **Le justificatif est optionnel par conception**, jamais bloquant (doc 04 §1).
5. **Statut/régime = configuration de premier rang par dossier, chaque dossier
   indépendant** (matrice doc 06 §7) : V1 opérationnelle sur SASU/EURL IS + option
   IR (bornée à 5 exercices, bascule tracée) avec TVA au réel ; les autres régimes
   arrivent par packs de données, jamais par refonte. Idem pour les **packs
   métier** par secteur (doc 03 §3bis).
6. **Deux modes d'usage, un seul moteur** : portefeuille (1 → N dossiers) et
   mono-entreprise (1 → 1) partagent modèle de données et écrans de niveau
   dossier (doc 01 §1, doc 11 §1bis). **Précisé le 2026-09-11 (doc 19)** :
   ce n'est plus qu'une question d'habillage UI — le gestionnaire
   portefeuille n'a **jamais accès** aux écrans de niveau dossier
   (transactions, justificatifs, clôture, signature), c'est l'indiv
   propriétaire du dossier qui les voit, quel que soit le mode. Le
   gestionnaire voit un état des lieux agrégé, point (doc 19 §2.1/§2.4).
7. **ML hiérarchique à 3 niveaux** : socle global de catégorisation → adaptation
   par client/pack → profil comportemental statistique **par dossier** pour les
   anomalies (« ce chauffeur a consommé plus que d'habitude ») — sans entraîner un
   modèle par chauffeur (doc 07 §3.3).

## Les 2 points à traiter en priorité absolue

1. **Auditer les 10 ans de données** — en particulier vérifier que le lien
   « libellé bancaire → imputation comptable » existe (doc 07 §2.1). C'est le
   risque n° 1 du projet. Le lien est vérifié (2026-09-02) ; la relecture des
   500 lignes qui donne la vraie mesure ML en est à 7/500 au 2026-11-05
   (AXE-423).
2. ~~Collecter la liste exacte statut par chauffeur~~ **Annulé le 2026-09-26** :
   tous les formats seront codés (doc 12, J2).

## Comment faire vivre cette doc

- Chaque document porte un statut (`brouillon à valider` → `validé le JJ/MM`).
- Les décisions techniques ponctuelles iront dans `docs/adr/` (1 page par décision).
- Toute évolution de périmètre passe par une mise à jour de doc, pas par un accord oral.
