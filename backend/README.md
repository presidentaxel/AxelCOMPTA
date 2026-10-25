# backend/ — axelcompta

Monolithe modulaire Python (FastAPI / SQLAlchemy / Postgres), découpage complet
défini en [doc 03 §3](../docs/03-architecture.md#3--découpage-en-modules-monolithe-modulaire).

> **Statut au 2026-09-05 : doc 17 semaines 0 à 3 faites.** Une commande
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
sans doublon. Le menu Démo ne sait pas effacer des à-nouveaux : une clôture
faite sur la démo reste.

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
le 2026-09-21) et `scripts/creer_comptes_demo_chauffeurs.py` (les 3 comptes
chauffeur de démo Karim/Sophie/Yanis, `app_metadata.env: "demo"` pour les
distinguer de vrais comptes pilote plus tard).

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

| Module | Rôle en une ligne | Démo (doc 17) | V1 (doc 12) |
|---|---|---|---|
| [`core/`](axelcompta/core/README.md) | Types partagés : monnaie, erreurs, ids typés | Actif (minimal) | Actif |
| [`tenants/`](axelcompta/tenants/README.md) | Tenants, dossiers, statuts/régimes | Réduit (1 dossier en dur) | Actif |
| [`packs/`](axelcompta/packs/README.md) | Packs métier : taxonomies, règles, templates | Actif (règles + mapping compte) | Actif |
| [`ingestion/providers/`](axelcompta/ingestion/providers/README.md) | Interface `DataProvider` + implémentations | Actif | Actif |
| [`documents/`](axelcompta/documents/README.md) | Justificatifs, OCR, Factur-X, matching | Non prévu | Actif |
| [`categorize/`](axelcompta/categorize/README.md) | Pipeline règles → ML → LLM → revue humaine | Actif (règles + ML, pas de LLM) | Actif |
| [`anomaly/`](axelcompta/anomaly/README.md) | Détection d'abus / anomalies | Non prévu | Actif |
| [`ledger/`](axelcompta/ledger/README.md) | ❤️ Moteur comptable pur | Actif | Actif |
| [`closing/`](axelcompta/closing/README.md) | Clôture d'exercice, états financiers | Actif (compte de résultat + bilan simplifiés) | Actif |
| [`filings/`](axelcompta/filings/README.md) | Renderers FEC, PDF, EDI-TDFC, INPI | Actif (liasse simplifiée, overlay CERFA 2065 partiel, dossier greffe/INPI démo — doc 20) | Actif |
| [`workflow/`](axelcompta/workflow/README.md) | Validation, revue, signature électronique | Actif (décisions humaines, revue, signature démo — doc 17 §9, doc 20) | Actif |
| [`api/`](axelcompta/api/README.md) | Routes FastAPI, auth, permissions | Réduit (pas d'auth) | Actif |
| [`ml/`](axelcompta/ml/README.md) | Entraînement, évaluation, registry modèles | Non prévu (modèle déjà entraîné réutilisé) | Actif |

## Ce qui existe déjà et sera réutilisé (hors de cet arbre)

Le travail d'audit dans [`_AUDIT_DONNEES/`](../_AUDIT_DONNEES/README.md) n'est
pas dupliqué ici : `packs/` et `categorize/` s'y réfèrent directement (pack
VTC, modèle TF-IDF entraîné, CSV FEC labellisé). Voir [doc 17 §4bis](../docs/archive/17-plan-demo-journal-2026-09.md#4bis-ce-quon-réutilise-déjà-accélérateurs-issus-de-laudit).
