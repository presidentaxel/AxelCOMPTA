# backend/ — axelcompta

Monolithe modulaire Python (FastAPI / SQLAlchemy / Postgres), découpage complet
défini en [doc 03 §3](../docs/03-architecture.md#3--découpage-en-modules-monolithe-modulaire).

> **État au 2026-11-05** : l'état du projet est tenu dans le
> [doc 12](../docs/12-roadmap-todo.md) ; la carte des modules dans le
> [doc 18](../docs/18-organisation-code.md). L'API se lance avec
> `uvicorn axelcompta.api.app:app` (section « Lancer l'API de démo »).
> Après un `git pull`, `alembic upgrade head` avant l'API. Le bloc
> ci-dessous date du 2026-09-05 et n'est gardé que pour l'historique.

> **Statut au 2026-09-05 (historique) : doc 17 semaines 0 à 3 faites.** Une commande
> unique produit un PDF **qui ressemble enfin à un compte de résultat + un
> bilan** (doc 17 §2 : « coupe verticale d'abord », semaine par semaine on
> remplace les bouchons par du réel). Ventilation TVA réelle (golden test
> Uber doc 13 §5.3 reproduit exactement, cas Bolt autoliquidation testé),
> vraie réconciliation (montant ±1 centime, fenêtre de date, libellé), vraie
> clôture simplifiée (compte de résultat + bilan qui s'équilibre : trésorerie
> = résultat + TVA à payer). Le « reste des transactions » (carburant,
> péage...) passe par règles + ML existant (`categorize/`), accepté sans
> revue humaine (`workflow/auto_accept.py` — stand-in, pas l'architecture
> cible). Postgres + Alembic montés et vérifiés contre un vrai conteneur,
> pas encore branchés dans `demo.py` (qui tourne en mémoire). **Aucun accès
> réel** aux API Digifactory/Rollee (token 401, sandbox non vérifié).
> `documents`, `anomaly`, `ml` n'ont toujours que leur `README.md` +
> `__init__.py`. **Doc 17 semaines 0 à 4 toutes faites** (2026-09-05) :
> semaine 4 tourne sur 3 vrais dossiers (`demo_multi_dossiers.py`) et a fait
> remonter un vrai bug (11/12 règles du pack sans indicateur insensible à la
> casse — le CA détecté d'un dossier passe de 591 € à 11 937 € une fois
> corrigé). Ajouté hors plan initial, demandé explicitement : overlay sur le
> vrai formulaire CERFA 2065-SD officiel (ADR-006) et exports FEC/grand
> livre/balance (doc 06 §6) — le détail légal derrière les chiffres de la
> liasse, pour un contrôle ou pour tracer une erreur.

## Faire tourner la démo (doc 17 semaines 0-3 + CERFA 2065)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m axelcompta.demo
# → liasse.pdf, cerfa_2065.pdf, journal.fec.txt, grand_livre.csv, balance.csv
# dans backend/_demo_output/
```

Aucune base de données requise : `demo.py` utilise `InMemoryLedgerService`.
La couture prouvée : fixtures (settlement Uber 1 040,00 € / transaction
+848,00 € UBER BV, + deux transactions « reste » : carburant, péage) →
`reconcilier()` (doc 13 §4.2) → écriture ventilée TVA pour le settlement
(`construire_ecriture_settlement`, doc 13 §5.3) ou écriture catégorisée pour
le reste (règles + ML via `RulesAndMlPipeline`, puis
`construire_ecriture_categorisee`) → `ClotureSimplifieeService` (compte de
résultat + bilan, doc 17 semaine 3) → deux renderers au choix :
`PdfLiasseSimplifieeRenderer` (lisible, pas de mise en page officielle) ou
`PdfCerfa2065Renderer` (résultat, exercice, régime, comptabilité
informatisée remplis sur le vrai formulaire officiel — identité
d'entreprise volontairement blanche). Vérifié : le bilan s'équilibre
(trésorerie = résultat + TVA à payer), la somme des soldes de tous les
comptes vaut exactement 0, et "728,15" apparaît bien dans la vraie case du
vrai PDF officiel (relu visuellement).

## Faire tourner la démo sur un vrai dossier complet (doc 17 §2, §7bis)

Le run ci-dessus tourne sur 3 transactions (golden test). Pour voir la
chaîne tenir sur un vrai dossier — 543 transactions réelles, exercice 2024
complet, résultat négatif (déficit) :

```bash
.venv/bin/python -m axelcompta.demo_dossier_reel
# → backend/_demo_output/liasse_dossier_reel.pdf
# → backend/_demo_output/cerfa_2065_dossier_reel.pdf (case Déficit remplie)
```

Nécessite le CSV audit (`_AUDIT_DONNEES/resultats/fec_ml_taxonomie.csv`,
gitignored — présent sur ce poste, pas forcément sur un clone frais). Voir
doc 17 §7bis pour le détail, dont un vrai bug de mapping compte-par-catégorie
trouvé en construisant ce test (corrigé, pas juste noté).

## Postgres + Alembic

```bash
# DATABASE_URL doit être définie (voir ../.env.example — déjà alignée par
# défaut sur docker-compose.yml, ne pas écraser un .env existant)
docker compose up -d --wait db   # --wait : bloque jusqu'au healthcheck OK
                                  # (sans --wait, "Started" ≠ prêt à accepter
                                  # des connexions — Postgres redémarre en
                                  # interne juste après le premier lancement)
.venv/bin/alembic upgrade head
docker compose down -v           # arrête et supprime les données (dev only)
```

Le schéma (`dossiers`, `ecritures`, `lignes_ecriture`) est défini par module
(`tenants/orm.py`, `ledger/orm.py`) sur une `MetaData` partagée
(`core/db.py`) ; `migrations/env.py` lit `DATABASE_URL` (jamais une valeur
figée dans `alembic.ini`). `PostgresLedgerService` (`ledger/repository.py`)
est l'implémentation réelle de `LedgerService` contre cette base — testée en
intégration (voir plus bas), pas encore branchée dans `demo.py`.

## Reproduire les vérifications

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q                       # suite rapide (doc 08 §4 étape 5), sans DB
.venv/bin/mypy axelcompta tests migrations  # strict, doit rester à 0 issue
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/lint-imports                     # frontières de dépendance (doc 03 §3)
```

Pour l'intégration (doc 08 §4 étape 6, nécessite Postgres — voir ci-dessus) :

```bash
# Base DÉDIÉE aux tests, toujours locale : chaque test fait `drop_all` en fin
# d'exécution. La fixture `engine` refuse (pytest.exit) toute base dont
# l'hôte n'est pas local, donc jamais la base Supabase de la démo.
docker compose up -d --wait db
docker compose exec db psql -U user -d postgres -c "CREATE DATABASE axelcompta_test"
export DATABASE_URL="postgresql://user:password@localhost:5432/axelcompta_test"
.venv/bin/pytest -q -m integration -k "not supabase"
```

Appels réels à Digifactory (hors CI, `DIGIFACTORY_TOKEN` dans le `.env`
racine) : `.venv/bin/pytest -q -m digifactory`. Le test ne garde aucun
libellé, IBAN ni nom.

Dossiers de démo branchés sur les contacts Digifactory (idempotent ;
`--formes` ne fait que reprendre la forme juridique depuis Sirene) :

```bash
set -a && . ../.env && set +a
.venv/bin/python scripts/ajouter_chauffeurs_digifactory.py
```

## Lancer l'API de démo sur Postgres (depuis le 2026-09-21)

L'API lit dossiers, ledger et propositions dans Postgres (elle ne les
recalcule plus à chaque requête). **Depuis le 2026-09-24, ce Postgres est
celui du projet Supabase** (ADR-003), plus le docker-compose local, qui ne
sert plus qu'aux tests d'intégration. `DATABASE_URL`, `DATABASE_URL_WEB` et
`AXELCOMPTA_WEB_PASSWORD` sont dans le `.env` racine (voir `.env.example`).
Une fois, puis à chaque nouveau schéma :

```bash
set -a && . ../.env && set +a
.venv/bin/alembic upgrade head
.venv/bin/python -m axelcompta.demo_seed      # idempotent, 3 dossiers de démo
.venv/bin/uvicorn axelcompta.api.app:app --port 8000
```

Au démarrage, l'API vérifie que la base est à la tête Alembic du code et
refuse de démarrer sinon (« lancer `alembic upgrade head` »). Sur un poste
de dev, `AXELCOMPTA_SCHEMA_NON_VERIFIE=1` saute la vérification (AXE-841).

**RLS depuis le 2026-09-22** (doc 03 §7, doc 12 §1.1) : `alembic upgrade
head` crée aussi le rôle `axelcompta_web`, restreint par des policies —
`DATABASE_URL_WEB` (voir `.env.example`) doit être défini avant de lancer
`uvicorn`, sinon `demo_api.py` refuse de démarrer (pas de repli silencieux
sur `DATABASE_URL`, ce qui ferait tourner l'API sans RLS). `DATABASE_URL`
reste celui des scripts d'administration ci-dessus (`demo_seed`,
`synchro_digifactory`, `notifier`), jamais soumis aux policies.

`python -m axelcompta.demo_seed` refuse de compléter un ledger à moitié
écrit (`AmorcageIncompletError`) : dans ce cas, vider les tables et relancer.

**Réamorçage obligatoire après le 2026-09-23** (doc 17 §15) : chaque
dossier de démo a désormais une écriture de libération du capital et une
identité légale. Une base amorcée avant cette date lève
`AmorcageIncompletError`. La base Supabase, créée le 2026-09-24, a été
amorcée après cette date : rien à faire. Pour repartir de zéro un jour, il
faut vider les tables applicatives du projet Supabase (dashboard, SQL
editor) avant `alembic upgrade head` et `demo_seed` ; les comptes Supabase
Auth (schéma `auth`) ne sont pas concernés.

Synchroniser les transactions Digifactory d'un portefeuille (nécessite
`DIGIFACTORY_BASE_URL`, `DIGIFACTORY_TOKEN` et des dossiers portant un
`contact_nr`) :

```bash
.venv/bin/python -m axelcompta.synchro_digifactory --tenant <tenant_id>
```

Idempotent et reprenable (curseur par dossier).

Prévenir les indivs qu'ils ont des opérations à confirmer : notification
interne (cloche de l'espace chauffeur), aucun e-mail. Un même dossier n'est
pas renotifié avant 6 h (sauf rappel à 7 jours).

```bash
.venv/bin/python -m axelcompta.notifier --tenant <tenant_id> --simulation  # sans rien enregistrer
.venv/bin/python -m axelcompta.notifier --tenant <tenant_id>
```

### Passer un dossier à l'exercice suivant

Seul le chauffeur clôt son exercice, depuis son écran Exercice
(`POST /dossiers/{id}/cloture-exercice`, attestation gardée mot pour mot).
La ligne de commande ne fait que simuler, pour vérifier un dossier :

```bash
.venv/bin/python -m axelcompta.exercices --dossier <dossier_id>
```

Refusé tant que l'exercice n'est pas terminé ou qu'une opération attend une
décision. La clôture passe en base les écritures d'inventaire et les
à-nouveaux, clôt l'exercice dans l'historique et ouvre le suivant (avenant
de régime en vigueur, sortie de franchise de TVA le cas échéant). Rejouable
sans doublon. Une clôture faite reste : rien ne l'efface (le menu Démo qui
remettait la démo à neuf a été retiré le 2026-11-05).

### Agrégats du portefeuille (AXE-566)

La page Entreprises ne reconstruit plus chaque dossier : elle lit les montants
de la liasse, l'exercice et l'alerte de franchise de TVA dans la table
`agregats_dossier`. Un trigger Postgres périme la ligne d'un dossier à chaque
écriture qui le concerne (écriture comptable, décision, provision de clôture,
modification du dossier), d'où qu'elle vienne : une route, la synchro
Digifactory, un script. Le statut d'invitation, les preuves de l'exercice et
la date du jour ne sont pas gardés, ils sont lus à l'affichage.

**Migration `e7b3d9a15c42` à appliquer avant de déployer l'API** (sans la
table, `GET /dossiers` échoue) :

```bash
set -a && . ../.env && set +a
.venv/bin/alembic upgrade head
.venv/bin/python -m axelcompta.agregats_portefeuille --tenant <tenant_id> --recalculer
```

La seconde commande remplit la table. Elle est facultative, mais sans elle la
première ouverture de chaque portefeuille calcule tous ses dossiers (mesuré :
huit secondes pour 200 dossiers de 300 écritures). Rejouable à tout moment,
même pendant que l'API tourne.

Pour contrôler qu'aucune invalidation n'a été manquée (lecture seule, code de
sortie 1 s'il y a un écart) :

```bash
.venv/bin/python -m axelcompta.agregats_portefeuille --tenant <tenant_id> --verifier
```

Si le calcul change sans qu'aucune écriture n'ait lieu (formule de la liasse,
matrice des statuts, seuils de franchise, pack métier), monter
`VERSION_CALCUL` dans `tenants/agregats.py` : les lignes calculées avec
l'ancienne version sont ignorées et recalculées au fil des ouvertures, ou
tout de suite avec `--recalculer --tout`.

### Tâches planifiées (cron)

`python -m axelcompta.taches` enchaîne, pour chaque portefeuille, la synchro
Digifactory (sautée si aucun dossier n'a de `contact_nr`) puis les
notifications. `scripts/taches_planifiees.sh` l'enveloppe pour un
planificateur : charge le `.env` racine s'il existe, empêche deux passages
simultanés (`flock`), écrit dans `_demo_output/journaux/taches.log`
(`AXELCOMPTA_JOURNAUX` pour changer). Installé sur le poste de démo le
2026-09-26, toutes les heures :

```
7 * * * * /chemin/vers/AxeLCompta/backend/scripts/taches_planifiees.sh
```

Sur le serveur de production, même script, sans `.env` : variables fournies
par le service (crontab de l'utilisateur ou timer systemd avec
`EnvironmentFile`), journaux dans `/var/log/axelcompta`. Retirer du poste :
`crontab -e` et supprimer la ligne.

Comptes Supabase : `scripts/creer_compte_gestionnaire.py` (gestionnaire),
`scripts/migrer_liens_vers_app_metadata.py` (comptes chauffeur créés avant
le 2026-09-21) et, jusqu'au 2026-11-05, `scripts/creer_comptes_demo_chauffeurs.py` (supprimé ; les 3 comptes
chauffeur de démo Karim/Sophie/Yanis, `app_metadata.env: "demo"` pour les
distinguer de vrais comptes pilote plus tard).

**Depuis le 2026-11-05 (mode réel)** : la base est celle du portefeuille
Serenity. Karim, Yanis, `demo@axelcompta.fr` et les comptes `demo-digi-*`
puis Sophie ont été supprimés : plus aucun dossier ni compte de démo en
base. Le paragraphe suivant est l'historique.

**Comptes de démo créés pour de vrai (2026-09-22)**, persistants — pas des
comptes de test supprimés après vérification comme jusqu'ici : deux comptes
gestionnaire (`louis.vedovato@axelproject.fr` et `demo@axelcompta.fr`, ce
dernier pour la personne à qui la démo sera montrée) et les 3 comptes
chauffeur (`demo-{karim,sophie,yanis}@axelcompta.fr`). Mot de passe
commun des trois chauffeurs, depuis le 2026-09-25 : `DemoChauffeur2026!`
(voir `frontend/README.md`). Les mots de passe gestionnaire restent hors
du repo. Pour en poser un autre :
`python scripts/reinitialiser_mot_de_passe.py <email>` (demandé au
clavier, jamais en argument).

**Mise à jour 2026-09-09** : `pytest`, `mypy axelcompta tests migrations`,
`ruff check .`, `ruff format --check .` et `lint-imports` passent tous à
0 erreur (182 tests rapides). Les deux écarts trouvés le 2026-09-08 (16
erreurs mypy dans des fichiers de test — annotations manquantes,
export implicite, narrowing `Optional` que mypy ne pouvait pas déduire
seul ; 4 fichiers jamais reformatés) sont corrigés.

**CI ajoutée le 2026-09-11** (`.github/workflows/ci.yml`, à la racine du
repo) : ces commandes ci-dessus (backend, y compris l'intégration contre un
vrai Postgres éphémère du job) + `next lint`/`next build` (front) tournent
maintenant automatiquement sur chaque push/PR vers `main`. Couvre les
étapes 1-6 du pipeline cible de [doc 08 §4](../docs/08-qualite-code.md) —
pas encore les étapes 7-10 (golden tests séparés, seuils de couverture,
audit dépendances/secrets, build Docker). Les tests marqués `supabase`
restent hors CI (quota e-mail réel, doc 17 §9 bloc B) — toujours manuels.

## Tests : un dossier miroir par module (doc 08 §3)

`tests/<module>/` reproduit exactement `axelcompta/<module>/` — c'est une
règle vérifiée, pas seulement une convention : `tests/test_code_quality.py`
fait échouer `pytest` si un module de `axelcompta/` n'a pas son dossier de
tests miroir avec au moins un `test_*.py`, ou si une fonction dépasse 60
lignes (doc 08 §1 règle 4). Ajouter un module = ajouter son dossier de tests
dans le même commit.

## Deux niveaux de lecture dans cet arbre

Ce découpage est celui du **produit final V1** (doc 03/12), pas seulement de
la démo. Chaque README de module précise donc deux statuts distincts :

- **Démo (doc 17)** : ce que ce module doit faire pour la démo interne d'un
  mois, scope volontairement réduit (voir [doc 17 §3](../docs/archive/17-plan-demo-journal-2026-09.md#3-coupes-de-scope-assumées)).
- **V1 cible (doc 12)** : ce que ce module doit faire pour le produit réel,
  à capacité normale (1-2 devs, phases pluri-mensuelles).

Un module marqué « non prévu pour la démo » existe déjà dans l'arbre (dossier
+ README) mais reste vide de code tant que sa phase n'est pas atteinte —
l'idée est de ne jamais avoir à ré-organiser l'arbre plus tard, seulement à
le remplir.

Détail complet de la correspondance arbre ↔ docs : [docs/18-organisation-code.md](../docs/18-organisation-code.md).

## Règles de dépendance (vérifiées par import-linter en CI, doc 03 §3)

- `ledger` ne dépend de rien sauf `core`. Jamais de `categorize`, `ml`, `api`.
- `categorize` produit des `ProposedEntry` ; seul `workflow` peut les
  transformer en écritures via `ledger`, après validation.
- `api` n'importe que les façades publiques de chaque module (`module/service.py`).
- Personne n'importe `ml` au runtime : les modèles sont chargés comme artefacts.

## Modules

| Module | Rôle en une ligne | État au 2026-11-10 | Manque pour la V1 |
|---|---|---|---|
| [`core/`](axelcompta/core/README.md) | Types partagés : monnaie, erreurs, ids typés, accès DB, métriques | Actif | — |
| [`tenants/`](axelcompta/tenants/README.md) | Tenants, dossiers, matrice statut × régime, avenants, agrégats, tags, Sirene, import CSV | Actif (tous statuts sauf micro), création en masse (AXE-809), Sirene (AXE-834), tags (AXE-829), configuration confirmée (AXE-730) | Identité de la société (AXE-846), INSEE/RNE (AXE-849) |
| [`packs/`](axelcompta/packs/README.md) | Packs métier : taxonomies, règles, templates | 21 règles, plancher par règle (AXE-826, AXE-837) | Taxonomie relue (AXE-815) |
| [`ingestion/providers/`](axelcompta/ingestion/providers/README.md) | Interface `DataProvider` + implémentations | Digifactory réel, comptes retenus et 512x (AXE-729, AXE-832), settlements sur fixtures | Relevés Uber/Bolt (AXE-801), import FEC (AXE-804), Rollee (AXE-817 à 821) |
| [`documents/`](axelcompta/documents/README.md) | Justificatifs, OCR, Factur-X, matching | Stockage en base (AXE-425) | OCR, matching, WORM |
| [`categorize/`](axelcompta/categorize/README.md) | Pipeline règles → ML → LLM → revue humaine | Virements internes, règles, modèle v2, catégorie Bridge ; arrêt sans modèle (AXE-825) | LLM branché, mesure (AXE-816), modèle hors du poste (AXE-847) |
| [`anomaly/`](axelcompta/anomaly/README.md) | Détection d'abus / anomalies | Détecteurs V1 (AXE-437, AXE-836), qualifications en base (AXE-814) | Jeu d'évaluation |
| [`ledger/`](axelcompta/ledger/README.md) | ❤️ Moteur comptable pur | I2, I3, I4, I7 tenus (AXE-806, AXE-807), contre-passation, sous-comptes 512x | I8 : Test Compta Demat (AXE-484) |
| [`closing/`](axelcompta/closing/README.md) | Clôture d'exercice, états financiers | Liasse 2033/2031, réel normal en totaux, CA3 annuelle et par période (AXE-805) | Immobilisations (AXE-802), LOA (AXE-803), bilan d'ouverture (AXE-804) |
| [`filings/`](axelcompta/filings/README.md) | Renderers FEC, PDF, EDI-TDFC, INPI | FEC validé, CERFA 2065/2031/2033, dossier INPI | Test Compta Demat (AXE-484), signature RGS (AXE-441) |
| [`workflow/`](axelcompta/workflow/README.md) | Validation, revue, notifications, signature | Décisions en OD de reclassement (AXE-420), quarantaine (AXE-424), expert-comptable (AXE-800), rappels envoyés (AXE-808) | Signature RGS (AXE-441) |
| [`api/`](axelcompta/api/README.md) | Routes FastAPI, auth, permissions | `api.app`, rôles dont expert, MFA, `/metrics` à jeton, erreurs 4xx | Routes hors `demo_api` et fichiers `demo_*` renommés (AXE-840) |
| [`pseudonymize/`](axelcompta/pseudonymize/) | Seule porte vers un LLM | Fait (AXE-436) | Fournisseur branché |
| [`jobs/`](axelcompta/jobs/) | File de jobs Postgres (ADR-002) | Utilisée par le worker (AXE-809, AXE-845, AXE-808) | — |
| [`ml/`](axelcompta/ml/README.md) | Entraînement, évaluation, registry modèles | Entraînement dans `_AUDIT_DONNEES/` | Registry, dérive |

## Ce qui existe déjà et sera réutilisé (hors de cet arbre)

Le travail d'audit dans [`_AUDIT_DONNEES/`](../_AUDIT_DONNEES/README.md) n'est
pas dupliqué ici : `packs/` et `categorize/` s'y réfèrent directement (pack
VTC, modèle TF-IDF entraîné, CSV FEC labellisé). Voir [doc 17 §4bis](../docs/archive/17-plan-demo-journal-2026-09.md#4bis-ce-quon-réutilise-déjà-accélérateurs-issus-de-laudit).

## Worker de la file de jobs (AXE-845)

Le bouton « Synchroniser » d'Entreprises et « Ajouter » sur un nouveau
chauffeur déposent une demande ; `scripts/worker_planifie.sh` (chaque minute,
sous `flock`) l'exécute avec le rôle propriétaire : création des dossiers
acceptés, détection des contacts Digifactory sans dossier, synchro, caches.

    * * * * * /chemin/vers/AxeLCompta/backend/scripts/worker_planifie.sh

## Mettre en route les tickets du 05 au 10/11 sur une base existante

Le code mergé ne suffit pas : sur la base réelle, il faut aussi (suivi dans
AXE-842) :

1. `alembic upgrade head` (l'API refuse de démarrer sur une base en
   retard, AXE-841).
2. Variables d'environnement (voir `.env.example`) : `METRICS_TOKEN` (sans
   lui, `/metrics` répond 404, AXE-810), `AXELCOMPTA_CLE_INTEGRATIONS` (clé
   qui chiffre les paramètres SMTP et SMS des gestionnaires, AXE-808).
   `AXELCOMPTA_SANS_MODELE=1` seulement en dépannage : sans modèle, la
   synchro s'arrête (AXE-825).
3. Reprises, en simulation d'abord, puis avec `--appliquer` (rejouables
   sans doublon) :

       python scripts/ventiler_comptes_bancaires.py --tenant TENANT --appliquer   # AXE-832
       python scripts/materialiser_decisions.py --tenant TENANT --appliquer       # AXE-420

4. Crontab : `taches_planifiees.sh` (chaque heure) et `worker_planifie.sh`
   (chaque minute).
5. Compte de test, si besoin (AXE-822, à supprimer avant que les
   chauffeurs se connectent) :
   `python scripts/compte_de_test.py creer <e-mail> --jusqu-au <date>`.

## Modèle de catégorisation hors du poste (AXE-847)

Le `.joblib` est gitignoré. Il vit dans un bucket S3 **privé**
(`MODELES_BUCKET`, `modeles` par défaut ; Supabase Storage en mode S3), un
dossier par version : modèle, empreinte `.sha256`, calibration, rapport.
Au démarrage du worker, de la synchro, des tâches planifiées et de l'API,
la version `AXELCOMPTA_MODELE_VERSION` est téléchargée si elle manque sur le
poste (ou si le fichier local ne respecte plus son empreinte), empreinte
vérifiée avant d'écrire. Sans stockage configuré, rien n'est tenté : la
synchro s'arrête d'elle-même sans modèle (AXE-825).

Publier une version, après accord sur le rapport d'entraînement
(simulation par défaut ; une version publiée ne se remplace pas) :

    python scripts/publier_modele.py tfidf_logreg_v2 \
        --rapport ../_AUDIT_DONNEES/resultats/rapport_modele_v2.txt --publier

Mise en route : créer le bucket privé `modeles` dans Supabase Storage, et
des clés d'accès S3 (Storage > S3 Connection) posées en `S3_ENDPOINT`,
`S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` sur le poste et le serveur.

## Registres officiels INSEE et RNE (AXE-849)

Chaque dossier qui a un SIREN est relu au plus une fois par semaine par les
tâches planifiées. Les écarts avec la déclaration du dirigeant apparaissent
dans Entreprises et bloquent la clôture et la liasse jusqu'à son choix.

Mise en route (rien ne se passe sans) :

1. Créer une clé API Sirene sur le portail de l'INSEE (`INSEE_API_KEY`) et
   un compte RNE sur data.inpi.fr (`INPI_RNE_USERNAME`,
   `INPI_RNE_PASSWORD`).
2. Vérifier la lecture sur un SIREN réel, sans rien écrire :
   `python -m axelcompta.registres_officiels --siren 123456789`.
3. Poser le SIREN des dossiers existants : `scripts/ajouter_chauffeurs_digifactory.py --sirene`
   (le reprend du contact Digifactory).

