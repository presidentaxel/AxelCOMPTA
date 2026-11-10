# 08 — Qualité de code : standards « NASA-grade » adaptés au projet

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-12

## 1. D'où on part : les règles NASA/JPL, et ce qu'on en garde

Les « Power of Ten » de Gerard Holzmann (NASA/JPL, 2006) ont été écrites pour du C
embarqué critique. On ne les copie pas bêtement : on les **transpose** à un système
Python/TypeScript dont la criticité est *l'exactitude comptable et l'auditabilité*,
pas le temps réel. Voici la transposition, règle par règle :

| Règle NASA originale | Transposition AxeLCompta |
|----------------------|--------------------------|
| 1. Flux de contrôle simple (pas de goto/récursion) | Pas de récursion non bornée ; complexité cyclomatique ≤ 10 par fonction (mesurée par ruff/radon en CI) ; pas de métaprogrammation maligne. |
| 2. Toutes les boucles ont une borne prouvable | Toute boucle sur données externes a une limite explicite (pagination max, taille de fichier max, timeout). Aucun `while True` sans compteur/timeout. |
| 3. Pas d'allocation dynamique après init | Sans objet en Python. Transposé : pas d'état global mutable ; les ressources (connexions, gros buffers) sont créées au démarrage et gérées par cycle de vie explicite. |
| 4. Fonctions ≤ 60 lignes | Fonctions courtes, une responsabilité. Limite dure : 60 lignes logiques (lint). |
| 5. ≥ 2 assertions par fonction | Transposé en **programmation par contrat** : pré/post-conditions sur les fonctions du domaine, invariants du ledger (doc 06 §1) vérifiés à l'exécution. Les assertions critiques restent actives en production. |
| 6. Données au plus petit scope | Pas de variables de module mutables ; injection de dépendances explicite ; dataclasses/modèles **frozen** par défaut. |
| 7. Vérifier toutes les valeurs de retour et entrées | Pas d'exception avalée (`except Exception: pass` interdit par lint) ; toutes les entrées externes validées par Pydantic à la frontière ; erreurs métier typées (`Result`/exceptions dédiées), jamais de codes magiques. |
| 8. Préprocesseur limité | Sans objet. Transposé : pas de monkey-patching, pas de `__getattr__` dynamique dans le code métier, configuration explicite plutôt que conventions cachées. |
| 9. Pointeurs restreints | Sans objet. Transposé : pas d'alias mutables partagés ; les fonctions du domaine reçoivent et retournent des objets immuables. |
| 10. Tous les warnings activés, zéro toléré | mypy `--strict`, ruff exhaustif, `tsc --strict`, eslint : **zéro warning en CI**. Une suppression (`# type: ignore`) exige un commentaire justificatif et est comptée (budget suivi). |

## 2. Principes maison (au-dessus des règles)

1. **Le code du domaine comptable est pur.** `ledger/` : pas d'I/O, pas d'horloge
   système (le temps est un paramètre), pas d'aléatoire. Conséquence directe :
   testabilité totale et bugs reproductibles.
2. **Parse, don't validate.** Les données franchissent les frontières en devenant
   des types riches (`Money`, `Siren`, `ExerciceOuvert`) ; à l'intérieur, plus
   besoin de re-vérifier — les types rendent les états invalides irreprésentables.
3. **Les flottants sont interdits pour l'argent.** Type `Money` (centimes entiers),
   lint custom qui interdit `float` dans `ledger/`, `closing/`, `filings/`.
4. **Toute écriture en base passe par une transaction** aux bornes explicites.
   Niveau d'isolation documenté là où ça compte (numérotation séquentielle).
5. **Append-only pour les faits.** On n'UPDATE pas un fait comptable ou un label
   d'entraînement ; on ajoute un événement qui le remplace.
6. **Tout comportement non déterministe est isolé derrière une interface** (LLM,
   horloge, aléatoire, réseau) — mockable, et le système doit survivre à sa panne.
7. **La config est validée au démarrage** (schéma Pydantic Settings). L'application
   refuse de démarrer avec une config invalide — jamais de défaut silencieux.

## 3. Conventions concrètes

### Python (backend)
- Python 3.12+, `from __future__ import annotations`.
- **mypy strict** sur tout le code, pas d'exception par module.
- ruff (lint + format) avec règles : complexité, longueur de fonction, imports
  triés, docstrings obligatoires sur les façades publiques.
- import-linter : contrats de dépendance entre modules (doc 03 §3).
- Nommage du domaine **en français** (`ecriture`, `dotation`, `liasse`) : c'est le
  vocabulaire du métier et des textes réglementaires ; l'anglais pour la technique
  (`repository`, `service`). Règle à fixer maintenant pour ne jamais mélanger.

### TypeScript (frontend)
- `tsc --strict`, eslint + typescript-eslint, prettier.
- Types générés depuis l'OpenAPI du backend (openapi-typescript) : **jamais de
  types API écrits à la main** — une seule source de vérité.
- Composants purs par défaut ; état serveur via TanStack Query ; pas de logique
  métier comptable dans le front (le front affiche, le back décide).

### Git et revues
- Trunk-based léger : branches courtes, PR obligatoires même à 2 devs — la revue
  croisée est notre seul « second regard » humain.
- Conventional Commits (`feat:`, `fix:`, `refactor:`…) → changelog généré.
- Un commit qui touche `ledger/` ou `filings/` exige : tests ajoutés/modifiés dans
  le même commit + mention de l'invariant concerné dans le message.
- `CODEOWNERS` : les modules critiques exigent l'autre dev en relecteur.

### Règles vérifiées automatiquement (pas seulement écrites ici)
- **Fonctions ≤ 60 lignes** (règle 4 ci-dessus) : vérifié exactement (comptage
  de lignes par l'AST, pas une approximation) par
  `backend/tests/test_code_quality.py::test_aucune_fonction_ne_depasse_60_lignes`,
  qui tourne à chaque `pytest` (étape 5 ci-dessous). Doublé par le seuil ruff
  `PLR0915` (max-statements, backend/pyproject.toml) en garde-fou supplémentaire —
  un proxy par nombre d'instructions, pas de lignes, donc pas suffisant seul.
- **Chaque module a ses tests** : `test_chaque_module_a_ses_tests` (même
  fichier) vérifie que chaque package sous `backend/axelcompta/` a un dossier
  miroir sous `backend/tests/` avec au moins un fichier `test_*.py` — un module
  ajouté sans test fait échouer la CI, pas seulement la revue humaine.

### Documentation dans le code
- Chaque module : `README.md` court (rôle, frontières, invariants).
- Chaque décision structurante : ADR dans `docs/adr/` (modèle 1 page).
- Les règles fiscales codées citent leur source (article, BOFiP, millésime) en
  commentaire — un auditeur doit pouvoir vérifier.

## 4. CI : la barrière de qualité (tout est bloquant)

```text
Pipeline CI (GitHub Actions), ordre d'exécution :
1. ruff format --check + ruff check          (style, complexité)
2. mypy --strict                              (types backend)
3. tsc --noEmit + eslint                      (front)
4. import-linter                              (frontières de modules)
5. pytest : unit + propriétés                 (rapide, < 5 min)
6. pytest : intégration (Postgres éphémère)   (transactions, RLS, migrations)
7. Tests golden : FEC, liasses, templates d'écritures
8. Couverture : ledger/closing/filings ≥ 95 %, global ≥ 85 % (seuils bloquants)
9. Audit dépendances (pip-audit, npm audit) + scan secrets (gitleaks)
10. Build images Docker + test de démarrage (smoke)
```

Règle d'équipe : **un main rouge bloque tout le monde** ; la priorité absolue est
de le remettre au vert, pas de contourner.

## 5. Gestion des erreurs : doctrine

- **Erreurs attendues** (fichier illisible, consentement expiré, LLM en panne) :
  modélisées dans les types de retour, traitées, visibles dans l'UI, jamais des 500.
- **Erreurs de programmation** (invariant violé) : on **s'arrête** (fail-fast),
  Sentry, alerte. Un invariant comptable violé ne se « rattrape » pas en silence —
  plutôt un job arrêté qu'un grand livre faux.
- **Dégradation par étage** (doc 05) : panne LLM → la file de revue humaine grossit,
  le système continue. Panne Bridge → les imports fichiers fonctionnent. Panne ML →
  les règles dures continuent. Le seul composant sans mode dégradé est Postgres,
  et c'est assumé (sauvegardes PITR, restauration répétée).
- **Idempotence des jobs** : tout job de fond peut être rejoué sans effet de bord
  (déduplication par clé naturelle, upserts contrôlés).

**API (AXE-839)** : une `DomaineError` répond 4xx avec son message, par un
seul gestionnaire (`axelcompta/api/erreurs.py`). Le code vient de la famille
de l'erreur (`core/errors.py`) : `Conflit` → 409, `Introuvable` → 404,
`SaisieInvalide` → 422, `Interdit` → 403 (AXE-800), sinon 400. Une route ne rattrape une erreur métier
que pour changer la réponse (message différent, autre forme). Un bug
(`InvariantViole`, toute autre exception) reste un 500.

## 6. Dépendances

- Toute nouvelle dépendance = mini-revue : maintenance, licence, surface d'attaque.
  À 2 devs, chaque dépendance est un passif.
- Versions épinglées (lockfiles), renouvellement mensuel via PR automatique
  (Renovate/Dependabot) — jamais de montée de version implicite.
- Interdiction des dépendances « pratiques » dans `ledger/` : le cœur n'a droit
  qu'à la bibliothèque standard + Pydantic.

## 7. Définition of Done (toute fonctionnalité)

- [ ] Code + tests (unitaires, et intégration si frontière touchée).
- [ ] mypy/ruff/eslint zéro warning ; couverture non dégradée.
- [ ] Contrats Pydantic mis à jour si une frontière change (+ OpenAPI régénéré).
- [ ] Journalisation/audit trail si l'action est métier (qui, quoi, quand).
- [ ] Doc module ou ADR mise à jour si une décision a été prise.
- [ ] Revue par l'autre dev.
- [ ] Démo possible sur staging avec données synthétiques.

## Migrations Alembic (AXE-841, 6 nov. 2026)

* **Une seule tête.** `tests/core/test_schema.py` échoue en CI si deux
  migrations partent de la même révision, et dit laquelle rebrancher.
* **Rebaser juste avant le merge.** Une PR qui ajoute une migration se
  rebase sur `main` juste avant d'être mergée ; son `down_revision` pointe
  sur la tête de `main` à ce moment-là.
* **Supabase après le merge, jamais avant.** `alembic upgrade head` se lance
  sur la base du portefeuille une fois la PR mergée. Pas de `stamp` pour
  rattraper un schéma posé à la main.
* **Le schéma suit le modèle** (AXE-854). `tests/integration/test_migrations.py`
  compare, après `upgrade head`, le schéma des migrations au modèle ORM
  (tables, colonnes, contraintes), vérifie la RLS sur toute table qui porte
  `dossier_id` ou `tenant_id`, et qu'un `downgrade base` ne laisse rien. Un
  écart voulu s'ajoute à `ECARTS_VOULUS`, avec sa raison.
* **L'API vérifie au démarrage** que la base est à la tête du code
  (`axelcompta/core/schema.py`) et refuse de démarrer sinon, avec la
  commande à lancer. `AXELCOMPTA_SCHEMA_NON_VERIFIE=1` saute la vérification
  sur un poste de dev, jamais en production.

