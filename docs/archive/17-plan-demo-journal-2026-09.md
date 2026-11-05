# 17 — Plan de démo produit (UX + moteur réel)

> **Statut : plan de sprint révisé, remplace la version précédente de ce
> doc.** Pivot décidé avec Louis le 2026-09-06 : l'ancien plan (« coupe
> verticale backend, front minimal en semaine 4 ») est **faux maintenant**.
> Le principe change : on construit d'abord le parcours complet des deux
> interfaces produit (gestionnaire PC, chauffeur mobile — détail dans
> [doc 19](../19-parcours-utilisateur.md)), avec de **vrais calculs** tournant
> sur un **jeu de données synthétique mais réaliste**, plutôt que l'inverse.
> Le travail déjà fait sur le moteur (§12) n'est pas jeté — il devient le
> cœur qu'on branche derrière ces deux interfaces.
> Dernière mise à jour : 2026-09-06.
>
> **Mises à jour ultérieures (2026-09-21/22), qui rendent périmés plusieurs
> passages ci-dessous** (« tout recalculé à chaque requête », « gestionnaire
> sans login », « `user_metadata.dossier_id` ») : l'API lit désormais
> dossiers, ledger et propositions en Postgres (`demo_seed` les amorce), le
> gestionnaire est authentifié par le lien `tenant_id`, et le lien chauffeur
> est dans `app_metadata`. Détail et raisons : [doc 18](../18-organisation-code.md).

## 1. Objectif de la démo

Faire tourner **le produit dans son ensemble** — pas juste le backend — sur
2-3 dossiers chauffeur fabriqués à la main mais crédibles : interface
gestionnaire (PC) + interface chauffeur (mobile) + moteur de calcul réel
(réconciliation, catégorisation, écritures, clôture, liasse). L'objectif
n'est pas la conformité DGFiP ni la gestion de tous les cas limites — c'est
de pouvoir dire **« ça marche, il reste à affiner »**, pas **« c'est un
jouet »**. Citation de Louis (2026-09-06) qui résume l'esprit : *« la démo
est un peu un produit final mais sans la précision de tout, donc tout
marche mais le résultat a le droit d'être un poil foireux »*.

## 2. Ce qui change par rapport à l'ancien plan

| Avant (jusqu'au 2026-09-05) | Maintenant |
|---|---|
| Coupe verticale backend d'abord, front minimal en dernier (rapport HTML) | UX des deux interfaces d'abord, moteur branché dessus dès que possible |
| Données = replay du CSV audit réel (36 152 lignes, bruit réel) | Données = 2-3 chauffeurs type fabriqués à la main (§4), propres mais réalistes |
| Calculs acceptés « estimés/simplifiés » | Calculs **réels** — objectif explicite : détecter si le moteur déconne, sur des données qu'on maîtrise |
| Chauffeur = jamais mentionné (front) | Chauffeur = une des deux interfaces de la démo (doc 19) |
| Connexion bancaire = Digifactory uniquement | Deux modes visibles, un seul câblé en priorité (doc 19 §4) |

**Ce qui ne change pas** : le moteur déjà construit (§12) n'est pas
réécrit — reconciliation, catégorisation, écritures, clôture, liasse
gardent leur logique. Ce qui change, c'est le jeu de données qu'on leur
donne à manger, et le fait qu'on les branche derrière une vraie interface
plutôt qu'un rapport HTML de sortie.

## 3. Principe directeur (mis à jour)

**Le parcours utilisateur d'abord, le moteur dessous dès que possible.**
On ne construit pas une UI seule sur des données statiques mockées jusqu'au
bout — dès qu'un écran existe, on le branche sur le vrai moteur (déjà
construit) plutôt que d'attendre la fin. Le risque principal n'est plus
l'intégration technique (déjà prouvée, doc 17 historique §12) mais
**est-ce que le parcours donne envie et est-ce que le calcul reste juste
sur un cas qu'on maîtrise**.

## 4. Le jeu de données synthétique — 3 chauffeurs type

Fabriqués à la main pour être crédibles (volume, variété) sans tomber dans
les vrais cas limites du dataset historique (doc 07). Chacun exerce un
chemin de calcul déjà implémenté (§12) — aucun nouveau template à écrire,
seulement de nouvelles données à faire tourner dedans. Objectif explicite
de Louis : *« il faut 2/3 chauffeurs un peu différents, on veut voir
comment ça rend en gestion multicompte de façon claire »*.

### 4.1 Karim — SASU, IS, assujetti TVA (taux réduit 10%), Uber principalement

Le cas « propre » : le golden test déjà validé (doc 13 §5.3) devient son
mois type, répété sur 4 semaines avec de légères variations de volume.

```
Semaine type (× 4, montants variables ±15%) :
  Settlement Uber : brut 1 040,00 € TTC / commission 192,00 € TTC / net 848,00 €
  → 512 D 848,00 / 622x D 160,00 / 44566 D 32,00 / 706 C 945,45 / 44571 C 94,55
Charges du mois : carburant (~4× 55-70 €, Esso/Total), péage (~4× 8-12 €),
assurance auto (1× mensuelle), entretien (1× ponctuel, ex. Norauto).
Repas légitimes hors domicile (2-3× dans le mois) : McDonald's/Quick — pas
présumés personnels (doc 07 §4, BOFiP).
```

Sert de golden test **et** de "dossier de référence sans ambiguïté" pour
montrer que le cas nominal ne fait pas remonter de fausse alerte.

### 4.2 Sophie — EURL, IS, assujetti TVA, Uber + Bolt, une dépense personnelle ambiguë

Teste le mix de plateformes (autoliquidation Bolt, doc 13 §5.3 « cas
autoliquidation ») et la file de revue humaine :

```
Semaines paires : settlement Uber (comme Karim, montants différents).
Semaines impaires : settlement Bolt — commission HT 160,00 €, autoliquidation
  UE : 44566 D 32,00 / 44571 C 32,00 (impact trésorerie nul, obligatoire
  pour la CA3, doc 13 §5.3).
Une dépense carte pro à consonance personnelle dans le mois (ex. achat Zara
ou Sephora, ~60-80 €) — doit remonter dans la file de revue comme
« à justifier / usage personnel » (doc 06 §3.6, doc 11 §3.2), pas être
auto-acceptée. Sert à montrer que le pipeline distingue le nominal de
l'à-trancher, pas seulement à calculer juste.
```

### 4.3 Yanis — franchise TVA, Uber uniquement, véhicule en LOA

Teste le régime franchise (pas de TVA collectée, doc 13 §5.3 « cas
franchise ») et le financement en LOA (doc 06 §3.5). **Uber, pas Bolt** :
combiner franchise et commission en autoliquidation UE (Bolt) pose une
vraie question fiscale (l'obligation d'autoliquider peut subsister malgré
la franchise) volontairement laissée hors scope démo — seule la
combinaison franchise + `france_20` est implémentée (§5).

```
Settlement Uber : brut 1 040,00 € (pas de TVA collectée), commission
  192,00 € TTC non récupérable (franchise) :
  512 D 848,00 / 622x D 192,00 (TTC) / 706 C 1 040,00
Loyer LOA mensuel (378 € TTC) : passé en 613 (locations) via la
catégorisation courante — pas de split déductible/non déductible pour cette
démo (doc 06 §3.5 : la ventilation fine reste V1, hors scope §8).
```

### 4.4 Ce que ces trois profils prouvent ensemble

Trois régimes TVA (assujetti/franchise), les deux plateformes du pilote
avec leurs deux traitements TVA différents, un cas nominal, un cas à
trancher par un humain, un cas avec immobilisation financée — sans sortir
une seule fois du périmètre déjà documenté et déjà codé. C'est le test de
« gestion multicompte claire » demandé : le gestionnaire doit voir au
premier coup d'œil que ces trois dossiers sont dans des états différents.

## 5. Le moteur réutilisé tel quel

Rien ne change dans la logique de calcul déjà construite (détail complet
en §12 et [doc 18](../18-organisation-code.md)) :

| Module | Rôle | Statut |
|---|---|---|
| `ingestion/reconciliation.py` | Matching settlement ↔ transaction bancaire | Fait, inchangé |
| `ingestion/ecritures_settlement.py` | Ventilation TVA Uber/Bolt/franchise | Fait — **étendu le 2026-09-06** : `tva_recettes_regime` en paramètre, franchise ajoutée (§9 semaine 1) |
| `categorize/rules_and_ml.py` | Règles pack VTC + modèle ML pour le reste des transactions | Fait, inchangé |
| `workflow/auto_accept.py` | Stand-in pour la revue humaine (démo seulement) | Fait — **remplacé dans la démo produit** par la vraie file de revue humaine (doc 11 §3.1) côté UI, puisque Sophie (§4.2) doit être tranchée par un humain, pas auto-acceptée |
| `closing/bilan_simplifie.py`, `filings/*` | Clôture, liasse, CERFA 2065, FEC, grand livre, balance | Fait, inchangé |

Seul `workflow/auto_accept.py` change de rôle : il servait de bouchon
d'auto-validation en l'absence d'UI ; la démo produit a maintenant une
vraie file de revue humaine à montrer, donc le stub n'est plus la solution
pour tous les cas — seulement un fallback si le temps manque pour brancher
l'écran de revue derrière chaque profil.

## 6. Les deux interfaces de la démo

Détail complet du parcours dans [doc 19](../19-parcours-utilisateur.md). Pour
la démo précisément :

- **Interface gestionnaire (PC/web)** : dashboard des 3 dossiers, file de
  revue réelle sur la dépense ambiguë de Sophie, clôture et liasse par
  dossier — s'appuie directement sur doc 11, rien de nouveau à concevoir
  côté écrans, seulement à construire.
- **Interface chauffeur (mobile/webapp)** : au moins un des trois profils
  (Karim, le plus simple) doit pouvoir être suivi côté chauffeur — voir ses
  transactions catégorisées, répondre à une question simple, signer.

## 7. Connexion bancaire dans la démo

Voir [doc 19 §4](../19-parcours-utilisateur.md#4-connexion-bancaire--deux-modes-par-dossier).
Résumé : mode `gestionnaire` (Digifactory) câblé en priorité — Louis
relance le fournisseur pour débloquer le token 401 (doc 16 §7) avant la fin
du mois. Mode `chauffeur_direct` : **si le temps le permet**, montré en
fonctionnement à la fin plutôt qu'en premier — pas bloquant pour juger la
démo réussie.

## 8. Coupes de scope assumées (mise à jour)

Ce qui reste hors scope, comme avant :
- Multi-tenant / RLS complet (les 3 dossiers de démo suffisent, un seul
  schéma).
- OCR réel des justificatifs (la photo s'attache à la transaction, le
  contenu n'est pas lu).
- Détection d'anomalies statistique (doc 05 §6.2) — la dépense ambiguë de
  Sophie est un cas écrit à la main, pas détectée par un modèle de profil.
- Signature électronique réelle (prestataire non choisi, ADR-004 toujours
  en attente) — simulateur d'écran suffit.
- Matrice complète statut × pack — seulement les 3 profils ci-dessus.

Nouveau, ajouté par ce pivot :
- **Pas de self-signup public** (doc 19 §3.1) — les comptes restent créés
  sur invitation, jamais par inscription libre. **Mise à jour 2026-09-07** :
  le flux d'invitation lui-même (gestionnaire invite un chauffeur par
  email, §9bis) devient un vrai écran à construire, pas un compte créé à la
  main en base — la nuance porte sur « pas de self-signup », pas sur
  « pas de vrai flux d'invitation ».
- **Pas de synchronisation API gestionnaire** (doc 19 §3.3) — prévue,
  documentée, pas construite ici.
- **Pas de app store réel** — la démo tourne en webapp, l'app native est un
  objectif post-démo (doc 19 §7).

Décidé le 2026-09-07 (voir §9bis pour le détail) :
- **Comptes réels via Supabase Auth**, pas un login simulé — exception
  assumée à ADR-003 (« jamais Supabase Auth »), notée dans l'ADR, à
  reprendre en implémentation maison avant la V1.
- **Dossier greffe/INPI en format réel** (PDF + données structurées, pas
  qu'un rendu visuel façon CERFA 2065) — plus proche de doc 02 §6 phase 1
  que des autres renderers de démo, avec un vrai risque de spike (schéma
  non documenté dans ce repo à ce jour, cf. §9bis).
- **Persistance réelle des décisions humaines** — la démo sort du régime
  « aucune persistance, tout recalculé à chaque requête » (`demo_api.py`
  actuel) pour les décisions de la file de revue et les comptes : ces deux
  objets doivent survivre entre deux requêtes. Le reste (transactions,
  écritures générées, liasse) peut rester recalculé à la volée.

## 9. Semaines et jalons

Repart de la coupe verticale déjà prouvée (§12) — on ne recommence pas de
zéro, on ajoute les deux interfaces autour du moteur existant.

### Semaine 1 — Jeu de données + branchement moteur

- Écrire les fixtures des 3 profils (§4) comme `NormalizedTransaction` +
  `PlatformSettlement`, au format déjà attendu par les providers existants.
- Vérifier que le moteur existant (§5) tourne sans modification dessus —
  seul un bug de mapping/règle serait acceptable à corriger (comme les deux
  déjà trouvés en semaine 4 de l'ancien plan, §12).

> **Fait (2026-09-06)** — `backend/axelcompta/ingestion/providers/chauffeurs_demo.py`
> (génération déterministe des 3 profils : courses agrégées en settlements
> hebdomadaires, dépenses récurrentes, la dépense ponctuelle de Sophie) et
> `backend/axelcompta/demo_chauffeurs_type.py` (composition root : rapport
> HTML + liasse/CERFA/FEC/grand livre/balance par chauffeur, sur le modèle
> de `demo_multi_dossiers.py`). Contrairement à `demo_dossier_reel.py`,
> aucun fichier gitignored requis — tourne sur n'importe quel clone.
>
> Le moteur n'a **pas** tourné sans modification, contrairement à
> l'hypothèse ci-dessus — écart trouvé en écrivant Yanis (franchise) plutôt
> qu'en testant après coup : `ingestion/ecritures_settlement.py` avait le
> taux de TVA recettes figé en dur à 10% assujetti (profil unique de
> l'ancien plan, doc 17 §3 d'origine) et ne savait pas du tout traiter la
> franchise. Ajouté `tva_recettes_regime` en paramètre (doc 13 §5.1,
> vocabulaire doc 14 §1.2) avec la branche franchise déjà décrite doc 13
> §5.3 — limitée à une commission `france_20` (§4.3). Une deuxième règle
> manquante trouvée pareillement : le pack réduit (12 règles) n'avait pas
> de règle LOA, ajoutée dans `_AUDIT_DONNEES/packs_vtc/regles_regex.csv`
> (donnée, pas du code). Les deux ont des tests dédiés
> (`tests/ingestion/test_ecritures_settlement.py`,
> `tests/ingestion/providers/test_chauffeurs_demo.py`).
>
> Résultat sur les 3 profils (200 jours actifs chacun, ~230 jours
> calendaires, seed déterministe) : 100% des settlements réconciliés,
> toutes les écritures équilibrées. CA plateforme sur la période : Karim
> 14 412 €, Sophie 13 375 € (Uber+Bolt), Yanis 12 584 € (franchise). Le
> compte d'attente 471 de Sophie contient bien la dépense Zara (68 €), pas
> auto-catégorisée sur un compte de résultat (doc 17 §11).
>
> **Poussé plus loin (2026-09-06), à la demande de Louis** (« on connaît les
> chiffres, autant pousser un peu ») — sans toucher au moteur cette fois,
> uniquement le jeu de données :
> - Montée en charge progressive (30 premiers jours actifs à volume réduit)
>   et congés (un bloc de repos forcé par profil), pas seulement le bruit
>   aléatoire d'1 jour sur 7.
> - Catégories supplémentaires sur les 3 dossiers : URSSAF (trimestriel),
>   honoraires comptable (semestriel), amendes ponctuelles.
> - **Karim** (le profil « nominal ») a maintenant une grosse réparation
>   isolée (890 €, distincte de l'entretien courant) et surtout **un
>   règlement dont le virement arrive hors fenêtre de réconciliation**
>   (doc 13 §4.2) : le settlement reste `en_attente_banque` (33/34 réconciliés,
>   pas 34/34), et son virement, lui, atterrit quand même en 706 brut via le
>   mode dégradé (doc 13 §6) — jamais exercé jusqu'ici. Un dossier par
>   ailleurs propre peut avoir un accroc ; le but est de voir la
>   réconciliation le reporter correctement, pas de fabriquer un cas
>   parfait partout.
> - **Sophie** passe d'une seule dépense ambiguë à quatre sur l'année (Zara,
>   Fnac, Sephora + une amende) — pour voir la file de revue avec du volume,
>   pas une anecdote.
> - **Yanis** change de loueur LOA en cours d'année (ALD Automotive à
>   378 €/mois jusqu'au jour 180, puis Arval à 410 €/mois) — un
>   renouvellement de contrat réel, pas un montant fixe sur toute la
>   période. Avec les URSSAF/honoraires en plus, son exercice ressort
>   maintenant **déficitaire** (-1 346,50 €) : exerce la case Déficit du
>   CERFA 2065 sur ce profil aussi (avant, seul le dossier réel de l'ancien
>   plan, doc 12 historique, y était jamais allé).
>
> Tests dédiés à chaque ajout dans
> `tests/ingestion/providers/test_chauffeurs_demo.py` et
> `tests/test_demo_chauffeurs_type.py` (135 tests passent au total, ruff/
> mypy/import-linter propres).

### Semaine 2 — Interface gestionnaire

- Dashboard 3 dossiers + fiche dossier (doc 11 §2) branchés sur les vraies
  données des 3 profils.
- File de revue réelle (doc 11 §3.1) sur la dépense ambiguë de Sophie —
  premier écran qui remplace un stub du moteur (`auto_accept`) par une
  vraie décision humaine dans l'UI.

> **Fait, en partie (2026-09-06)** — `backend/axelcompta/demo_api.py`
> (FastAPI, lecture seule : `/dossiers`, `/dossiers/{id}`,
> `/dossiers/{id}/transactions`) + `frontend/` (Next.js App Router,
> Tailwind sur les tokens `DESIGN.md`) : tableau de bord des 3 dossiers et
> fiche dossier avec liste des transactions, badge « à trancher » sur le
> compte d'attente 471 — les 3 dépenses ambiguës de Sophie s'y voient
> réellement, calculées par le vrai moteur (pas de données mockées côté
> front). Testé en vrai (API + Next.js lancés ensemble, doc 17 §9,
> commandes dans `frontend/README.md`), pas seulement en unitaire.
>
> **Pas fait** : la décision humaine elle-même (accepter/reclasser une
> écriture à trancher) — l'API ne sert que du GET. Volontaire : mieux vaut
> un écran de lecture réel et fini qu'une écriture à moitié câblée
> derrière. C'est la suite immédiate, pas reportée sine die.
>
> `demo_api.py` est une composition root distincte de `axelcompta/api/`
> (la vraie API produit, doc 03 §7, toujours un squelette) — elle peut
> importer `demo_chauffeurs_type.py` directement (règle des composition
> roots, doc 18), ce que `api/` n'aura jamais le droit de faire.

**Suite décidée le 2026-09-07** (discussion Louis/Claude Code sur le modèle
de décision humaine, doc 05 §5 précisé en conséquence). Trois blocs, dans
cet ordre — chacun est un prérequis du suivant :

**A. Persistance des décisions + trace d'audit — fait (2026-09-07).**
`workflow/decisions.py` (`DecisionHumaine` immuable, `AnnotationDev`
séparée, doc 05 §5), `decisions_memory.py` (tests rapides) et
`orm.py`/`decisions_postgres.py` (persistance réelle, deux tables
append-only, migration `55cf8c93e5bf`) — testé contre un vrai Postgres
(`tests/integration/test_decisions_repository.py`). Depuis le 2026-09-24,
`decisions_humaines` est aussi verrouillée en base (migration
`d8b41c6e0a27`) et chaque décision est recopiée dans `journal_audit`.
Détail dans `backend/axelcompta/workflow/README.md`.

**Pas encore fait, trouvé en cours de route** : `construire_ledger()`
(`demo_chauffeurs_type.py`) calcule la `ProposedEntry` de chaque
transaction catégorisée puis la jette une fois l'écriture construite — il
faut la retourner (ou l'exposer autrement) pour que le futur endpoint de
décision (bloc C) sache quoi mettre dans `etage_origine`/
`confiance_origine`. Refactor mineur mais réel, pas juste un branchement
direct — à faire au début du bloc C, pas oublié.

**Bug corrigé en marge** : `.env` pointait vers des identifiants Postgres
(`axel:axel`) qui ne correspondent pas à ceux du conteneur réellement
initialisé (`user:password`, doc 09 §4) — la connexion échouait
silencieusement tant que personne n'avait testé contre un vrai Postgres
depuis la démo. Corrigé dans `.env` (non versionné).

**B. Comptes réels (gestionnaire + chauffeur) via Supabase Auth.** Décidé
le 2026-09-07 : Supabase Auth plutôt qu'un login simulé, pour pouvoir dire
« ce sont de vrais comptes » — **exception assumée à ADR-003** (qui
proscrit Supabase Auth au profit d'une implémentation maison), documentée
dans l'ADR. **Mise à jour 2026-09-08 : Louis confirme rester sur Supabase
Auth au-delà de la démo, y compris pour la V1** — ce n'est plus une entorse
à reprendre, voir ADR-003 mise à jour du 2026-09-08 pour le compromis retenu
(le risque CLOUD Act de la base s'étend à l'auth, coût de sortie plus lourd
qu'un `pg_dump`). Inclut le flux d'invitation
gestionnaire → chauffeur (email) et les **deux variantes visibles** selon
`mode_acces_bancaire` (doc 19 §4) : le chauffeur relie sa propre banque
(`chauffeur_direct`), ou n'a qu'à accéder à l'app/ses infos sans rien
connecter (`gestionnaire`, cas pilote). Pas la priorité en soi, mais fait
maintenant puisque c'est le même chantier que « construire les comptes de
la démo ». **Estimation : ~1,5-2 jours** (premier vrai système d'auth du
projet, donc moins de terrain déjà connu que le reste).

> **Fait, préparation infra (2026-09-07)** — le projet Supabase existe et
> communique, aucun code applicatif encore écrit :
>
> - Projet Supabase créé par Louis (`axelcompta-demo`), lié à aucun repo
>   GitHub (décision : le lien sert au branching Supabase, incompatible
>   avec nos migrations Alembic — pas de valeur ajoutée pour l'instant, et
>   ça aurait donné à un tiers déjà noté comme risque (ADR-003, CLOUD Act)
>   un accès de plus). Compute au plus bas (ajustable plus tard sans
>   recréer le projet).
> - Sécurité projet : **Data API désactivée**, **Auto expose new table
>   désactivé** (cohérent avec ADR-003 : « jamais Supabase Auth/PostgREST »
>   — confirmé, le point 4 ci-dessous), **Auto RLS activé** (toute nouvelle
>   table verrouillée par défaut).
> - **Levé le 2026-09-24 (ADR-003) : la base applicative est désormais
>   sur ce même projet Supabase.** Texte d'origine conservé pour l'historique :
>   **Base applicative toujours séparée du projet Supabase** (décision du
>   2026-09-07, ci-dessus) : `DATABASE_URL` (docker-compose local) reste la
>   base de `workflow.decisions_humaines` etc. — Supabase n'héberge que
>   l'auth (schéma `auth`, propre au projet). Pas de risque de ralentir la
>   suite de tests : les tests rapides n'appellent déjà jamais Postgres
>   (`dependency_overrides`, bloc C), et la suite d'intégration reste sur
>   le Postgres local.
> - 4 clés dans `.env`/`.env.example` (non versionné pour les valeurs
>   réelles) : `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
>   `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.
> - **Connectivité vérifiée en réel** (pas en théorie) :
>   1. Les deux clés décodent avec le bon `role` (`anon`/`service_role`) et
>      le bon `ref` de projet.
>   2. `GET /auth/v1/health` répond (service GoTrue vivant).
>   3. `anon` refusé sur les routes admin (403 `not_admin`) — la clé
>      publique n'a pas de pouvoir d'admin.
>   4. `service_role` a un vrai accès admin (`GET /admin/users` → 200,
>      liste vide sur un projet neuf).
>   5. `SUPABASE_JWT_SECRET` vérifié en le faisant vraiment servir : un
>      token signé à la main avec ce secret est accepté par Supabase
>      (erreur `user_not_found` — la signature est validée, seul
>      l'utilisateur inventé n'existe pas). Preuve que le futur backend
>      pourra vérifier des tokens Supabase sans rappeler l'API à chaque
>      requête.
>   6. `disable_signup` mis à `true` par Louis dans le dashboard
>      (Authentication → Sign In / Providers) — **vérifié** : `POST
>      /auth/v1/signup` en `anon` renvoie maintenant `422
>      signup_disabled` (doc 19 §3.1 : pas de self-signup public).
>   7. **Vérifié séparément que ça ne bloque pas le flux d'invitation
>      futur** : une création d'utilisateur via `service_role`
>      (`POST /admin/users`, sans email envoyé) réussit malgré
>      `disable_signup: true` — ce réglage ne gouverne que l'endpoint
>      public `/signup`, jamais les routes admin. Utilisateur de test créé
>      puis supprimé immédiatement après (projet resté vide).
>
> **Pas encore fait (à cette date)** : tout le code applicatif — aucune
> dépendance Supabase dans `backend/`/`frontend/`, aucun modèle de compte,
> aucune table `users`/liaison `dossier ↔ compte`, aucun écran de
> connexion, pas de flux d'invitation. Ce qui précède est de l'infra
> vérifiée, pas une fonctionnalité.

> **Fait (2026-09-08) — flux d'invitation gestionnaire → chauffeur, un
> premier morceau du bloc B, pas tout le bloc.**
>
> - `demo_comptes.py` : `CompteRepository` (frontière), `Invitation`/
>   `StatutInvitation` (2 états modélisés — `invité`/`actif` ; `non_invité`
>   représenté par l'absence, `compte_créé`/`inactif` de doc 19 §3.2 pas
>   modélisés, demanderaient un suivi applicatif que Supabase seul ne
>   fournit pas), `SupabaseCompteRepository` (Supabase est la seule source
>   de vérité — chaque utilisateur invité porte `user_metadata.dossier_id`,
>   pas de table séparée à synchroniser).
> - `demo_comptes_memory.py` : `InMemoryCompteRepository`, pour que la
>   suite rapide ne dépende jamais de Supabase (Louis, 2026-09-07).
> - **Placé délibérément hors du découpage doc 03 §3** (composition root
>   de démo, comme `demo_api.py`) plutôt que dans `tenants`/`api` — cette
>   séparation reste valable même après la mise à jour du 2026-09-08
>   (Supabase Auth confirmé pour la V1, ADR-003) : `tenants`/`api`
>   accueilleront le vrai système de comptes en V1 (toujours via Supabase,
>   pas réécrit maison), mais le câblage démo (`demo_comptes.py`) reste une
>   composition root de démo, pas le code cible — étendre leur graphe de
>   dépendances maintenant pour du code de démo aurait été une vraie
>   décision de structure, pas prise ici.
> - `demo_api.py` : `POST /dossiers/{id}/inviter` (envoie un vrai e-mail
>   via Supabase, pas de simulateur) + `statut_invitation` sur
>   `DossierResume`. Même idiome que `get_decisions` (bloc A) :
>   `get_comptes` construit le client Supabase à la première requête
>   réelle, jamais à l'import.
> - Écran : `InvitationActions.tsx` sur le tableau de bord (doc 19 §3.2 :
>   « écran de premier rang », pas la fiche dossier) — badge si
>   invité/actif, formulaire e-mail sinon.
> - Testé : 8 tests unitaires (mémoire) + 4 tests contre le **vrai**
>   projet Supabase (`tests/integration/test_comptes_supabase.py`,
>   marqueur `supabase`, skip sans credentials) qui créent un utilisateur
>   via `/admin/users` (jamais d'e-mail envoyé par cette route) pour
>   vérifier `statut()`, plus la garde anti-double-invitation. **Un
>   cinquième test existe mais reste désactivé exprès**
>   (`test_inviter_envoie_une_vraie_invitation`) : c'est le seul qui
>   appelle réellement `/invite` et consomme un envoi du quota e-mail
>   Supabase (très limité sur le tier gratuit) — à lancer manuellement
>   quand Louis est d'accord, pas en routine.
> - **Corrigé (2026-09-08)** : la corruption disque (`errno 117`) qui
>   bloquait `uvicorn` a été traitée en reconstruisant `backend/.venv` à
>   neuf (`rm -rf .venv && python3 -m venv .venv && pip install -e
>   ".[dev]"`) plutôt qu'en rafistolant les paquets touchés — aucun autre
>   artefact trouvé ailleurs dans le repo (`_AUDIT_DONNEES/.venv`,
>   `frontend/node_modules` sains). La vérification en vrai navigateur,
>   bloquée depuis, a pu être faite (voir bloc ci-dessous).
>
> **Connexion chauffeur, `mode_acces_bancaire`, et retrait partiel du
> stub — fait (2026-09-08).**
> - `demo_auth.py` (nouveau, composition root comme `demo_comptes.py`) :
>   vérifie les jetons Supabase côté chauffeur. **Découverte en testant
>   contre un vrai jeton de connexion** : ce projet Supabase signe en
>   **ES256 via les « JWT Signing Keys » (JWKS)**, pas en HS256 avec
>   `SUPABASE_JWT_SECRET` — la vérification du 2026-09-07 (« un jeton
>   signé à la main avec ce secret est accepté par Supabase ») testait
>   autre chose (que Supabase accepte ce secret comme preuve d'identité
>   envers ses propres routes admin), pas que les jetons *émis* par
>   Supabase soient signés avec. `SUPABASE_JWT_SECRET` n'est donc plus
>   utilisée par ce module — la vérification se fait contre la clé
>   publique du JWKS (`jwt.PyJWKClient`), aucun secret à connaître côté
>   serveur. Détail dans le commentaire de module de `demo_auth.py`.
> - `GET /dossiers/{id}` et `GET /dossiers/{id}/transactions` acceptent
>   maintenant un en-tête `Authorization: Bearer` optionnel : absent →
>   comportement inchangé (cas gestionnaire, pas de login) ; présent et
>   valide mais pour un autre dossier → 403 (doc 19 §4 : un chauffeur ne
>   voit que son propre dossier) ; invalide/expiré → 401.
> - `mode_acces_bancaire` ajouté à `ProfilChauffeurType` et à
>   `DossierResume` — Karim en `chauffeur_direct`, Sophie/Yanis en
>   `gestionnaire` : les deux modes doc 19 §4 sont donc représentés dans
>   la démo, visibles en badge sur le dashboard (doc 17 §7).
> - Frontend : `app/chauffeur/{login,accepter-invitation,[dossierId]}` +
>   `lib/auth-chauffeur.ts` (appels REST directs à Supabase Auth, jamais
>   le SDK `@supabase/supabase-js` — même choix que le backend, ADR-003).
>   Restructuration du routage en groupe `app/(gestionnaire)/` pour que
>   l'habillage gestionnaire (Sidebar/TopBar) ne s'applique plus qu'aux
>   routes gestionnaire (doc 19 §7 : « même socle, deux habillages ») —
>   sans effet sur les URLs existantes.
> - **Vérifié en vrai navigateur** (pas seulement en test) : utilisateur
>   chauffeur créé via `/admin/users` (pas `/invite`, pas de coût quota
>   e-mail) puis supprimé après coup — connexion réelle, transactions de
>   Karim affichées via le vrai moteur, tentative d'accès au dossier de
>   Sophie renvoyée vers son propre dossier, déconnexion puis nouvelle
>   tentative renvoyée vers `/login`. Dashboard gestionnaire et fiche
>   dossier (bloc C) revérifiés sans régression après la restructuration
>   du routage.
> - **Décision prise avec Louis (2026-09-08) sur la portée de
>   `UTILISATEUR_DEMO`** : le stub n'est retiré que côté chauffeur.
>   L'action de tranchage (bloc C) reste gestionnaire, et le dashboard
>   gestionnaire n'a délibérément pas de login pour l'instant — ce n'est
>   pas dans ce lot. `UTILISATEUR_DEMO` reste donc en place pour
>   `_trancher()`, avec un commentaire explicite (pas un oubli). Un
>   chantier d'auth gestionnaire séparé serait nécessaire pour le retirer
>   complètement.
> - Parcours mobile complet (transactions détaillées avec vocabulaire
>   dédié, question de catégorisation, photo, signature — doc 19 §5
>   points 5-8) : **toujours la Semaine 3**, pas ce lot. Ce qui est fait
>   ici (login, session, une vue transactions minimale en lecture) en est
>   le prérequis direct.
> - Découvert en passant, pré-existant, pas causé par ce lot : `mypy
>   axelcompta tests migrations` (commande documentée dans backend/README)
>   a 16 erreurs dans des fichiers de test jamais touchés ici
>   (`test_chauffeurs_demo.py`, `test_demo_chauffeurs_type.py`), et `ruff
>   format --check .` a 4 fichiers non formatés — le README affirme
>   « tout passe à 0 erreur » depuis le 2026-09-05, ce n'est plus vrai. Ni
>   l'un ni l'autre n'a été corrigé ici (hors scope de ce lot) — à traiter
>   séparément.

**C. Écran de revue réelle sur la dépense de Sophie — fait (2026-09-07).**
`workflow/revue.py` (reclassification 471 → compte réel, 455 pour « usage
personnel » selon la forme juridique, doc 06 §3.6) + endpoint
`POST /dossiers/{id}/transactions/{ecriture_id}/decision` (`demo_api.py`,
FastAPI `Depends`/`dependency_overrides` pour ne pas coupler la suite de
tests rapide à un Postgres démarré) + bouton réel dans la fiche dossier
(`TrancherActions.tsx`, composant client Next.js). Vérifié en HTTP réel
(`curl`, POST puis GET qui reflète la décision, retenter la même écriture
refusé en 409) **et** dans un vrai navigateur (clic → Postgres →
`router.refresh()` → la ligne Zara passe de 471/« à trancher » à
455/« validé »). `nb_a_trancher` (dashboard) reflète la résolution.

**Choix pour la démo, pas la version finale** : le champ libre "autre
catégorie" (reclassification hors usage personnel) est un simple champ
texte, sans les alternatives suggérées par le pipeline ni les raccourcis
clavier de doc 11 §3.1 — cette richesse reste V1. Le stand-in
`UTILISATEUR_DEMO` (un seul utilisateur fictif) attribue toutes les
décisions tant que le bloc B (comptes réels) n'existe pas.

### Semaine 3 — Interface chauffeur

Suppose le bloc B (comptes réels) déjà fait — sinon Karim n'a nulle part où
se connecter.

- Parcours mobile de Karim (doc 19 §5, sous-ensemble démo — pas les 8
  étapes du doc, uniquement celles utiles à la démo) : connexion (compte
  Supabase Auth créé via l'invitation du bloc B), transactions
  catégorisées, une question de catégorisation, photo de justificatif
  (attachée à la transaction, pas d'OCR — doc 17 §8), signature **mockée**
  (décidé 2026-09-07 : « vrai faux », pas de prestataire réel).
- Connexion bancaire mode `gestionnaire` visible (toggle) ; mode
  `chauffeur_direct` en construction si le temps le permet (§7) — l'écran
  d'invitation des deux modes est déjà fait au bloc B, ici c'est le
  parcours chauffeur qui en découle qui reste à construire.

**Estimation : ~1,5 jour.**

> **Fait (2026-09-09)** — question de catégorisation, photo, signature.
>
> **Décidé avec Louis avant de coder** : Karim (le profil « sans fausse
> alerte », doc 17 §4.1) n'a par construction aucune écriture à trancher —
> démontrer la question de catégorisation sur lui n'aurait rien à
> montrer. Plutôt que d'ajouter une dépense ambiguë à Karim (aurait
> contredit son statut documenté de cas nominal), **`trancher()` a été
> ouvert au chauffeur authentifié** (`demo_api.py` : `_verifier_acces_dossier`
> déjà en place côté lecture, étendu à cette route ; `decide_par` devient
> l'identité réelle du chauffeur au lieu de `UTILISATEUR_DEMO` quand il y
> en a une). C'est **Sophie** (qui a les dépenses ambiguës, §4.2) qu'il
> faut utiliser pour démontrer ce parcours en vrai, pas Karim — les deux
> peuvent avoir un compte chauffeur, `mode_acces_bancaire` ne conditionne
> pas qui a un login (doc 19 §4 vs §3.1, deux notions distinctes).
>
> - `QuestionCategorisation.tsx` : « Cette dépense est-elle personnelle ? »
>   Oui/Non — vocabulaire simple (doc 19 §5.5), même endpoint de décision
>   que le gestionnaire (`TrancherActions.tsx`), pas un nouveau mécanisme.
> - `demo_justificatifs.py` (nouveau, composition root de démo comme
>   `demo_comptes.py`/`demo_auth.py`, hors doc 03 §3) + endpoint
>   `POST .../justificatif` (upload multipart, content-type validé,
>   écriture vérifiée) + `JustificatifPhoto.tsx` (input caché,
>   `capture="environment"` pour ouvrir l'appareil photo mobile). Le
>   contenu n'est jamais lu (pas d'OCR, doc 17 §8) — `TransactionVue`
>   gagne juste `a_justificatif: bool`.
> - `SignatureMock.tsx` : « vrai faux » (décidé 2026-09-07), état local
>   seulement, pas persisté — ce n'est pas une `DecisionHumaine` à tracer.
> - Badge de connexion bancaire selon `mode_acces_bancaire` sur la page
>   chauffeur : message informatif (`gestionnaire`) ou bouton désactivé
>   « bientôt » (`chauffeur_direct`, toujours pas de vraie connexion —
>   Digifactory reste bloqué, doc 16 §7).
>
> Vérifié en vrai navigateur, pas seulement `tsc`/tests : connexion
> Sophie (compte Supabase de test créé via `/admin/users`, jamais
> `/invite`), question résolue en direct (Zara 471→455, `decide_par` =
> l'UUID Supabase réel de Sophie en base — vérifié en SQL direct, pas
> `gestionnaire_demo`), photo réellement écrite sur disque (confirmée
> côté fichier + refus 403 testé sur le dossier de Karim), signature
> mockée, badge `chauffeur_direct` vérifié sur Karim. Comptes de test
> supprimés après coup (projet Supabase resté vide, aucun coût d'e-mail).
>
> **Pas fait, hors scope de ce lot** : la connexion bancaire
> `chauffeur_direct` elle-même (le bouton est un stub désactivé, pas un
> vrai flux — toujours conditionné à Digifactory ou à un canal direct,
> doc 16 §8) ; gestion des rejets d'upload (taille de fichier, formats
> exotiques) au-delà de la validation du content-type.

### Semaine 4 — Clôture, liasse, dossier greffe, répétition

> ⚠️ **Écart trouvé le 2026-09-11, après coup** : tout ce qui suit dans
> cette section a été construit **sur la fiche dossier gestionnaire** —
> cohérent avec ce que doc 11/doc 19 disaient jusqu'au 2026-09-11. La
> révision du même jour (doc 19 §2.1/§2.4/§5.3) change ça : clôture et
> signature sont maintenant des écrans **indiv**, pas gestionnaire. Le
> code ci-dessous (`ClotureSection.tsx`, `GreffeInpiSection.tsx`, routes
> `demo_api.py`) reste **fonctionnellement correct** (bons calculs, bons
> tests) mais **au mauvais endroit** — à déplacer côté `/chauffeur/*`
> quand ce chantier sera codé (doc 19 §8), pas refait de zéro. Décision de
> Louis : documenter maintenant, coder plus tard.
>
> **Déplacé le 2026-09-11, même jour** (doc 19 §8) : `ClotureSection.tsx`
> et `GreffeInpiSection.tsx` vivent maintenant sur `/chauffeur/[dossierId]`,
> signature authentifiée (`signerGreffeInpiChauffeur`). Fiche dossier
> gestionnaire et `TrancherActions.tsx` supprimés. Vérifié en vrai
> navigateur (compte de test Sophie, supprimé après) : signature réelle en
> direct, dashboard gestionnaire sans navigation vers un détail. `next
> lint`/`build` verts, 232 tests backend inchangés (aucun code backend
> touché). Limite connue non corrigée dans ce lot : l'accès anonyme aux
> routes indiv de `demo_api.py` reste techniquement possible (doc 19 §8bis).

- Clôture + liasse + CERFA 2065 + FEC/grand livre/balance sur les 3
  dossiers (déjà fait au niveau moteur, §12) — exposés dans l'interface
  gestionnaire plutôt qu'un export PDF isolé. **Estimation : ~1 jour**
  (réutilise des renderers déjà faits, surtout du branchement front).

> **Fait (2026-09-11)** — `demo_api.py` gagne 5 routes de téléchargement
> (`GET /dossiers/{id}/{liasse.pdf, cerfa-2065.pdf, fec.txt,
> grand-livre.csv, balance.csv}`), toutes sur le ledger **avec décisions
> humaines appliquées** (`_construire_liasse` sur `_ledger_avec_decisions`,
> pas le ledger brut de `demo_chauffeurs_type.py`) — une écriture tranchée
> en 455/108 (bloc C) doit sortir de la liasse téléchargée, pas seulement
> du dashboard (vérifié par test : `test_fec_reflete_une_decision_tranchee_pas_le_ledger_brut`).
> Même contrôle d'accès que les autres routes dossier
> (`_verifier_acces_dossier` — un chauffeur ne peut pas télécharger la
> liasse d'un autre dossier). Côté front, `ClotureSection.tsx` (nouveau
> composant) affiche compte de résultat + bilan simplifié (CA HT/Charges/
> Résultat/Trésorerie/TVA à payer — ces deux derniers n'étaient nulle part
> à l'écran avant, seulement dans la réponse API) et les 5 liens de
> téléchargement, sur la fiche dossier gestionnaire. **Vérifié en vrai
> navigateur** sur les 3 profils (uvicorn + Postgres migré + Next.js
> lancés ensemble) : Karim (résultat positif, vert), Yanis (déficitaire,
> -1 346,50 €, rouge, TVA à payer 0 € en franchise), Sophie — pas
> seulement `tsc`/tests. 8 tests ajoutés
> (`tests/test_demo_api.py`), mypy/ruff/import-linter/pytest tous verts
> (214 tests backend), `next lint`/`next build` verts.
>
> **Pas fait dans ce lot** : le dossier greffe/INPI (item séparé
> ci-dessous, son propre spike) et la répétition avec run pré-cuit.
- **Nouveau, décidé 2026-09-07** : dossier de dépôt greffe/INPI en
  **format réel** (PDF + données structurées, doc 02 §6 phase 1) — pas un
  simple rendu visuel façon CERFA 2065.

> **Spike fait (2026-09-11)** — [doc 20](../20-integration-inpi-depot-comptes.md).
> Bonne surprise : contrairement à Digifactory avant le doc 16, l'INPI
> **documente publiquement** le schéma (`POST /api/annual_accounts`, doc
> 20 §3) — pas besoin d'attendre un contact fournisseur pour savoir quoi
> construire. Mauvaise surprise, différente de celle anticipée : le vrai
> blocage n'est pas le schéma (résolu) mais la **signature électronique
> qualifiée RGS** légalement obligatoire pour ce dépôt (C. com. art.
> R.123-5, doc 20 §4) — recoupe directement ADR-004 (prestataire de
> signature, toujours en devis, doc 12 §0.1). Tant qu'aucun prestataire
> qualifié n'est retenu, le dépôt réel via API n'est pas possible — seule
> la génération du dossier prêt à déposer **manuellement** (PDF + JSON,
> doc 02 §6 phase 1) reste réaliste à court terme.
>
> **Construit le même jour, suite immédiate décidée avec Louis** : « on
> fait la démo en pensant à la prod » — signature **fictive** en démo,
> mais une vraie abstraction (`workflow/signature.py`, `SignatureProvider`)
> que le futur prestataire (comparatif doc 20 §6) branchera sans réécrire
> le reste. `filings/inpi_depot.py` (payload JSON réel + PDF marqué
> « DOCUMENT FICTIF »), `demo_api.py` (`GET .../greffe-inpi.pdf`, `POST
> .../greffe-inpi/signature`), `GreffeInpiSection.tsx` (bouton « Signer
> (démo) » + badge). Vérifié en vrai navigateur sur Karim : clic réel,
> badge → « signé », PDF retéléchargé effectivement différent (filigrane
> rouge diagonal + ligne signataire/horodatage). 18 tests ajoutés, tout
> vert (232 tests backend, `next lint`/`build`). Détail complet :
> [doc 20 §5](../20-integration-inpi-depot-comptes.md#5-ce-que-ça-change-pour-le-plan-doc-17-§9-semaine-4-doc-12).

- Répétition avec un run pré-cuit en secours, comme dans l'ancien plan.

> **Répétition faite le 2026-09-11** — parcours réel en navigateur, pas
> un simple redémarrage des serveurs : dashboard (3 dossiers, Sophie « 3 à
> trancher ») → fiche Sophie (clôture, signature greffe/INPI, descente
> jusqu'à la dépense Zara) → **tranchage réel en direct** → dashboard
> re-vérifié (« 2 à trancher ») → fiche Yanis (déficitaire, TVA 0€ en
> franchise, chiffres cohérents avec les sessions précédentes).
>
> **Vrai accroc trouvé, pas un bug produit** : le premier essai a échoué
> (« Échec de la décision » à l'écran) — deux serveurs `next dev` tournaient
> en parallèle depuis une session précédente, celui utilisé écoutait sur le
> port 3001 au lieu de 3000. `ORIGINE_FRONTEND_DEV` (`demo_api.py`) est figé
> sur `http://localhost:3000` (doc 08 : pas de sur-ingénierie pour la démo)
> — le CORS a bloqué la requête sur le mauvais port. Cause identifiée,
> serveurs stray tués, rejoué sur le port 3000 : passe sans accroc. **Pas
> un bug de code, une leçon d'hygiène de répétition** — retenue pour la
> vraie présentation : vérifier qu'aucun `next dev`/`uvicorn` résiduel ne
> tourne avant de lancer, le port 3000 doit être libre.
>
> État de démo remis à zéro après coup (la décision Zara créée pendant la
> répétition a été supprimée de Postgres) — Sophie repart avec ses 3
> dépenses à trancher pour la vraie présentation, pas 2. Le run pré-cuit
> lui-même (rapport HTML + PDF, `python -m axelcompta.demo_chauffeurs_type`,
> doc 17 §12) reste valide et inchangé comme filet de secours si le live
> plante — pas rejoué ici, rien n'y a changé depuis sa dernière exécution.

> **Re-vérification backend après la refonte Postgres/auth (2026-09-22).**
> Cette répétition du 11/09 tournait sur l'ancienne architecture (tout
> recalculé à la volée, `UTILISATEUR_DEMO`). Le 21-22/09, l'API a changé de
> fond en comble (lecture Postgres, jeton Supabase obligatoire, `demo_seed`)
> — plus rien ne prouvait que le parcours démo tenait encore dessus. Vérifié
> pour de vrai, en curl avec de vrais jetons Supabase (pas de front lancé,
> voir juste en dessous pourquoi) :
> - Connexion réelle des 5 comptes de démo (§ ci-dessous) — jetons valides.
> - Dashboard gestionnaire : les 3 dossiers s'affichent avec les bons
>   agrégats (Yanis toujours déficitaire à -1 346,50 €, cohérent avec les
>   sessions précédentes).
> - Contrôle d'accès : 401 sans jeton, 403 quand Sophie appelle le dossier
>   de Karim.
> - File de revue réelle : Zara (Sophie) tranchée 471 → 455, vérifié aussi
>   dans le FEC téléchargé (la ligne 455 y apparaît, plus la 471).
> - Clôture : PDF liasse téléchargé, valide.
> - Greffe/INPI : signature démo posée sur Karim, le PDF change réellement
>   (filigrane), `qualifie: false` comme attendu.
> - État remis à zéro après coup, comme le 11/09 : décision Zara supprimée
>   de Postgres, `uvicorn` redémarré pour vider la signature INPI (en
>   mémoire, pas persistée) — Sophie confirmée de nouveau à 3 à trancher,
>   Karim confirmé `greffe_inpi_signe: false`.
>
> **Comptes de démo créés pour de vrai, cette fois persistants** (jusqu'ici
> les comptes de vérification étaient créés puis supprimés à chaque
> session) : deux comptes gestionnaire (`louis.vedovato@axelproject.fr` et
> `demo@axelcompta.fr`, ce dernier pour la personne à qui la démo sera
> montrée) et les 3 comptes chauffeur (`demo-{karim,sophie,yanis}@axelcompta.fr`,
> `app_metadata.env: "demo"`, aucun `tenant_id` — accès indiv seulement, pas
> de portefeuille). Nouveau script `scripts/creer_comptes_demo_chauffeurs.py`
> (doc 18, backend/README). Mots de passe donnés à Louis hors du repo.
>
> **Pas fait ici, donc pas prouvé** : le rendu écran (dashboard, file de
> revue, clôture, bouton signature) côté navigateur. `node`/`npm` sont
> absents de l'environnement Claude Code utilisé pour cette vérification —
> impossible d'y lancer `next dev`. Le backend tient, mais tant que
> personne n'a cliqué dans le vrai navigateur sur cette architecture,
> l'écran lui-même (rendu, régressions front éventuelles depuis le 11/09)
> reste une inconnue réelle, pas juste une formalité.

### Semaine 4bis — Design system V1 + passe UX/UI (ajouté 2026-09-09)

**Demande de Louis (2026-09-09)** : avant la démo, il faut une vraie V1
d'un design system (pas juste la spec de tokens) et une passe UX/UI pour
voir ce qu'on peut améliorer — ajouté ici explicitement pour ne pas s'y
prendre trop tard (« qu'on se mette pas dans le mur »). Pas encore scopé
en détail ni estimé — cette section capture le constat et l'intention,
pas un plan d'exécution figé.

**Écart réel trouvé en regardant le code (pas juste supposé)** :
[DESIGN.md](../../DESIGN.md) (v1.0) documente déjà une spec de composants
complète — `button-primary/secondary/ghost/danger`, `text-input`,
plusieurs variantes de `card`, `review-card`, tous les `badge-*` — mais
**aucun composant React ne les implémente**, à une exception près
(`frontend/components/Badge.tsx`, seul composant partagé qui existe).
Tout le reste construit cette session (`TrancherActions.tsx`,
`InvitationActions.tsx`, `QuestionCategorisation.tsx`,
`JustificatifPhoto.tsx`, `SignatureMock.tsx`) et les pages elles-mêmes
réinventent chacune leurs propres classes Tailwind au lieu d'importer un
composant partagé — un bouton "primaire" n'est nulle part le même
`className` d'un fichier à l'autre. Ce n'est pas une improvisation isolée
d'aujourd'hui : c'est l'état du frontend depuis le début de la démo,
juste plus visible maintenant qu'il y a plus d'écrans.

**Ce que ça implique, dans l'ordre** (à confirmer/prioriser avec Louis,
pas décidé ici) :
1. **V1 du design system = de vrais composants React** qui implémentent
   les tokens déjà écrits dans DESIGN.md (`Button.tsx`, `Card.tsx`,
   `TextInput.tsx`, les variantes de badge manquantes…) — combler l'écart
   entre la spec et le code, pas réinventer la spec.
2. Migrer les écrans existants (gestionnaire : dashboard, fiche dossier ;
   chauffeur : login, transactions) sur ces composants plutôt que sur
   leurs classes ad hoc actuelles.
3. **Une fois seulement** la V1 en place : la passe UX/UI proprement dite
   (revue visuelle des écrans réels, pas des maquettes) — c'est là que
   « voir ce qu'on peut faire » prend sens, sur une base cohérente plutôt
   qu'écran par écran sur du code qui sera de toute façon remplacé à
   l'étape 2.

**Pas fait ici** : aucun composant n'a été créé pour cette section, ni
estimation chiffrée — l'écart est documenté, la priorisation attend
Louis (avant Semaine 4 ? en parallèle ? après la démo ?).

> **Étape 1 (composants) faite le 2026-09-22**, décidée avec Louis comme
> priorité pour fermer la démo : `Button`/`Card`/`Input` (shadcn/ui, Radix +
> CVA) implémentant exactement les variantes DESIGN.md, `Badge.tsx` étendu
> aux 8 variantes du vocabulaire de statut (avant : 4, dont un `danger` hors
> vocabulaire). A nécessité une migration **Tailwind v3 → v4** au passage
> (le CLI shadcn ne génère plus que du code v4) — faite avec l'outil
> officiel `@tailwindcss/upgrade`, un seul renommage mécanique
> (`shadow-sm`→`shadow-xs`), build/lint vérifiés verts à chaque étape.
> Détail complet, y compris un aller-retour où le premier essai (avant la
> migration Tailwind) cassait la compilation : DESIGN.md § Known Gaps et
> § Correspondance Tailwind/shadcn-ui.
>
> Migré dans les écrans réels : dashboard gestionnaire (`DossierCard` →
> `Card`), formulaire d'invitation (`InvitationActions` → `Input`/`Button`).
> **Pas encore fait** : les écrans restants (`ClotureSection`,
> `GreffeInpiSection`, `Sidebar`, `TopBar`, `/connexion`, `/chauffeur/*`),
> ni l'étape 2 (passe UX/UI proprement dite, doc 17 §9 point 3 ci-dessus) —
> les deux attendent d'être scopées avec Louis, pas commencées ici.
>
> **Rendu visuel non vérifié dans le navigateur** cette session (extension
> Chrome non connectée) — vérifié uniquement par build/lint/HTTP 200. Le
> dev server tournait (`npm run dev`, port 3000) et répondait correctement,
> mais personne n'a regardé l'écran.

### Estimation globale et mise en garde sur les dates

**~8 à 11 jours de travail effectif** (A+B+C ≈ 3,5-4j, semaine 3 ≈ 1,5j,
semaine 4 ≈ 2j + 1-2j de spike greffe), pas 3 semaines calendaires — sauf
si le rythme du sprint du 02-06/09 (qui a abattu l'équivalent en ~5 jours)
ne se maintient pas maintenant que Louis est seul (doc 12, hypothèse de
capacité). Les labels « Semaine 3 »/« Semaine 4 » sont conservés pour ne
pas casser les renvois déjà écrits ailleurs (`demo_api.py`,
`frontend/README.md`, `workflow/README.md`) mais **ne correspondent à
aucune semaine calendaire précise** — à traiter comme des jalons de
contenu, pas des dates. **N'inclut pas la Semaine 4bis** ci-dessus
(design system V1 + passe UX/UI, ajoutée le 2026-09-09, pas encore
estimée) — à chiffrer une fois le périmètre précisé avec Louis.

## 10. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Token Digifactory toujours bloqué fin de mois | Le mode `gestionnaire` de la démo tourne sur les fixtures des 3 profils, pas sur l'API réelle — la relance Digifactory est en parallèle, pas sur le chemin critique de la démo |
| Vouloir montrer `chauffeur_direct` complet fait déraper le planning | Explicitement en dernier, explicitement optionnel (§7, §9 semaine 3) |
| La vraie file de revue humaine (nouveau vs `auto_accept`) prend plus de temps que prévu | Fallback : garder `auto_accept` pour Karim/Yanis (cas nominaux), ne construire l'écran de revue que pour le cas Sophie qui le justifie |
| Dérive de scope vers la matrice complète statut × pack | §8 rappelle explicitement les non-objectifs |
| ~~Schéma du dossier greffe/INPI inconnu~~ | **Résolu (2026-09-11)** : documenté publiquement par l'INPI, voir doc 20. Nouveau risque à sa place : signature qualifiée RGS obligatoire pour le dépôt réel, recoupe ADR-004 (prestataire non retenu) — bloque l'appel API, pas la génération du dossier prêt à déposer manuellement |
| Supabase Auth (nouveau, jamais utilisé dans ce projet) prend plus de temps que prévu à intégrer | Fallback : compte unique pré-créé par profil (Karim/Sophie/Yanis) sans vrai flux d'invitation par email si le temps manque — l'essentiel à montrer est « le compte existe et fonctionne », pas le parcours d'inscription complet |
| Persistance des décisions humaines mal isolée du reste (recalculé à la volée) fait resurgir une décision « oubliée » à la relecture suivante | Tests dédiés sur le stockage (bloc A) avant de brancher l'écran de revue (bloc C) — même logique que les golden tests existants |
| Design system V1 + passe UX/UI (§9 Semaine 4bis) pas scopée à temps, découverte en dernière minute avant la démo | Écart déjà documenté maintenant (2026-09-09), pas d'attendre la répétition pour le découvrir — reste à prioriser avec Louis (avant/en parallèle/après le reste de Semaine 4) |

## 11. Golden tests

Le golden test Uber existant (doc 13 §5.3, ancien §7 de ce doc) reste valide
tel quel — c'est exactement le mois type de Karim (§4.1). S'y ajoutent
deux golden tests supplémentaires, un par nouveau profil :

- **Sophie** : le mois complet doit produire une écriture usage-personnel
  (455/108) sur la dépense ambiguë **uniquement après validation humaine**
  dans la file de revue — pas d'auto-acceptation sur ce cas précis.
  **Vérifié côté moteur (2026-09-06)** : la dépense reste au compte
  d'attente 471, jamais auto-catégorisée (`tests/test_demo_chauffeurs_type.py`).
  **Vraie écriture 455 faite (2026-09-07)** : `test_trancher_en_usage_personnel_reclasse_vers_le_compte_455`
  (`tests/test_demo_api.py`) — via l'API réelle, pas un test isolé de la
  fonction de reclassification seule.
- **Yanis** : balance équilibrée avec le traitement franchise (pas de TVA
  collectée). **Fait (2026-09-06)** : `tests/ingestion/test_ecritures_settlement.py`
  et `tests/ingestion/providers/test_chauffeurs_demo.py`. Le suivi LOA
  hors-bilan (part non déductible séparée) n'est pas fait — la démo passe
  le loyer en charge simple (613), limite assumée (§4.3).

## 12. Historique — ce qui a déjà été fait (acquis, réutilisé §5)

L'ancien plan (semaines 0 à 4, du 2026-09-01 au 2026-09-05) a démontré que
la chaîne complète tient bout-en-bout sur données réelles, avant ce pivot :

- **Semaine 0** : squelette bout-en-bout, PDF produit en mémoire, Postgres/
  Alembic montés (pas encore branchés).
- **Semaine 1** : les 5 providers fonctionnels ; `FileImportProvider`
  rejoue le CSV audit réel (36 152 lignes).
- **Semaine 2** : réconciliation réelle (doc 13 §4.2), écritures ventilées
  TVA Uber/Bolt (doc 13 §5.3), règles + ML pour le reste.
- **Semaine 3** : clôture réelle (bilan qui s'équilibre), liasse simplifiée
  en PDF.
- **Hors plan initial** : overlay sur le vrai CERFA 2065-SD officiel
  (`filings/cerfa_2065.py`).
- **Semaine 4** : tourné sur 3 vrais dossiers du CSV audit (pas des
  fixtures) — **deux vrais bugs trouvés** : règles regex non insensibles à
  la casse (CA détecté passé de 591 € à 11 937 € une fois corrigé), mapping
  `recettes_plateformes` sur un mauvais compte.
- **Test dossier réel complet** (`demo_dossier_reel.py`) : un vrai exercice
  2024 rejoué (543 transactions), résultat négatif, case Déficit du CERFA
  2065 exercée pour la première fois.
- **Hors plan initial** : exports FEC + grand livre + balance
  (`filings/fec.py`, `filings/export_comptable.py`).

Détail complet, fichier par fichier, commandes de reproduction :
[doc 18](../18-organisation-code.md) et [backend/README.md](../../backend/README.md).
**Rien de ce travail n'est perdu** — c'est le contenu du §5 ci-dessus.

## 13. Rappel — ce plan n'est pas le roadmap

Les hypothèses de capacité, les phases et les critères de sortie du doc 12
restent la référence pour la trajectoire produit réelle. Ce doc 17 est un
sprint de preuve de concept isolé, pas une réduction du périmètre V1.

## 14. Retour de Louis, 2026-09-22 (soir) — chantiers ouverts pour demain

Trois points soulevés après avoir vu l'écran chauffeur pour de vrai
(`/chauffeur/DEMO_sophie`, comptes de démo créés le même jour). Notés ici
tels quels, **rien n'est tranché ni assumé** — à discuter avant toute
nouvelle itération de code dessus.

**Parcours chauffeur : à repenser, pas un problème de polish visuel.**
Verdict de Louis : « c'est pas trop mal mais c'est pas une app, c'est un
flow continuel vers le bas avec toutes les transactions ». Ce n'est pas la
même chose que l'écart design system déjà connu (Semaine 4bis ci-dessus,
qui est une question de composants/tokens) — c'est un problème de
structure de l'expérience elle-même. Louis veut une vraie session UI +
psychologie de l'utilisateur avant qu'un design soit choisi.
**Personne ne doit avancer une proposition d'écran seul avant cette
discussion** — à traiter en session dédiée, pas en continuant à itérer sur
l'écran actuel (liste unique qui défile, doc 19 §5.5) en attendant.

**Exports demandés en PDF** (aujourd'hui CSV, `filings/export_comptable.py`,
routes `/dossiers/{id}/{grand-livre.csv, balance.csv}` de `demo_api.py`) :
- Grand livre → PDF.
- Balance → PDF.
- FEC (`filings/fec.py`, .txt) : **pas de PDF demandé** — Louis ne sait pas
  ce qu'est le FEC, à lui expliquer d'abord (pas fait ce soir, explicitement
  reporté) avant de décider quoi que ce soit dessus.

**Liasse jugée insuffisante pour la démo.** Mots de Louis : « la liasse est
nulle, il me faut une vraie liasse, un truc qui fait officiel et bô ...
comme c'est une démo, il faut show off ». La liasse actuelle
(`filings/liasse_simplifiee.py`) est délibérément simplifiée depuis
l'origine (doc 17 §3 : « pas conforme CERFA/DGFiP », limite assumée pour
la démo) — mais ce n'est plus suffisant pour l'usage qu'il veut en faire.
Le vrai overlay CERFA 2065 existe déjà et tourne
(`filings/cerfa_2065.py`, doc 12 §0.3 « Hors plan initial ») : piste la
plus évidente pour un rendu plus sérieux, à vérifier/discuter demain
plutôt que décidé unilatéralement ici.

## 15. Traité le 2026-09-23 : exports PDF, FEC légal, liasse fiscale complète

Suite directe du §14. Trois décisions de Louis ce jour-là :

- **Grand livre et balance en PDF** : faits (PR #1, `filings/pdf_export_comptable.py`).
- **FEC** : pas de PDF, mais un format qui respecte **à la lettre** l'article
  A.47 A-1 du LPF. Écarts corrigés dans `filings/fec.py` : virgule décimale
  (le point était faux), `EcritureNum` en séquence continue et
  chronologique (au lieu des identifiants internes `settlement-34`),
  `CompteLib` jamais vide, zones nettoyées des tabulations et retours,
  enregistrements CR+LF, nom légal `<SIREN>FEC<AAAAMMJJ>.txt`. Les écritures
  d'inventaire (TVA, IS) y figurent, pour que le FEC concorde avec la liasse.
- **Liasse** : « un CERFA bien rempli, complet, on ne skip rien ». Faite sur
  les **vrais formulaires officiels 2026** : 2065-SD, 2065-bis-SD et 2033-A
  à G (régime simplifié d'imposition, celui d'une SASU/EURL de chauffeur),
  en un seul PDF (`/dossiers/{id}/liasse-fiscale.pdf`). Pas d'expert-comptable
  dans la boucle pour la démo, décision de Louis : la table comptes →
  rubriques (`closing/rubriques_2033.py`) suit la notice 2033-NOT-SD ligne à
  ligne, sans relecture professionnelle.

Ce qui a changé pour y arriver, au-delà du rendu :

- **Clôture fiscale** (`closing/cloture_fiscale.py`) : liquidation de la TVA
  (4457/4456 vers 44551), résultat fiscal avec réintégrations (IS en 324,
  amendes en 330), IS au taux réduit 15 % jusqu'à 42 500 € (proratisé) puis
  25 %, écriture 695/444, déficit reportable en 2033-D. Montants en euros
  entiers, écart d'arrondi du bilan absorbé par la rubrique la plus proche
  de sa valeur exacte.
- **Identité légale des dossiers** (`core/identite.py`, colonne
  `dossiers.identite`, migration `b3d91e7a2c40`) : dénomination, SIREN,
  siège, associés. Les 3 chauffeurs de démo reçoivent une identité
  **fictive** (`demo_identites.py`), SIREN à clé valide vérifiés non
  attribués dans l'annuaire des entreprises. Un dossier sans identité reste
  valide, en-têtes blancs (dossier historique pseudonymisé).
- **Capital social** : écriture de libération du capital au premier jour
  (512/1013). Sans elle, le 2033-A affichait un capital nul.
- **Amendes** : catégorie `amendes_infractions` sur 6712 (et plus 671),
  le compte que la clôture réintègre.
- **Exercice déclaré** : 06/01/2025 → 31/12/2025 (`Dossier.exercice_fin`),
  et non plus les dates de la première et de la dernière écriture.

Limites qui restent vraies : le PDF sert à relire et signer, le dépôt légal
reste dématérialisé (EDI/EFI) ; le 2033-C ne gère pas les cessions (pas de
registre des immobilisations) ; le FEC n'est pas passé dans « Test Compta
Demat » (outil Windows) ; une base de démo amorcée avant ce jour doit être
réamorcée (le ledger a une écriture de plus, `demo_seed` refuse de
compléter un ledger partiel).

## 16. Traité le 2026-09-24 : durcissement V1, prévu et hors démo

Rien de ce qui suit n'est dans le périmètre de la démo, et ce n'est pas une
dérive : c'était prévu. Ce sont des items V1 déjà listés dans doc 12
(§1.1 journal d'audit, §1.2 dashboard consentements, §1.3 verrous et
invariants), avancés pendant que la démo tient debout. Aucun écran de la
démo ne change.

| PR | Quoi | Où c'est suivi |
|---|---|---|
| #3 | scikit-learn épinglé en 1.9.0 (version qui a sérialisé le modèle) | `backend/pyproject.toml` |
| #4 | Signature greffe persistée en Postgres, même modèle que les décisions | doc 18, doc 20 |
| #5 | Écriture validée non modifiable (trigger, invariant I2) | doc 12 §1.3 |
| #6 | Consentement bancaire classé à chaque synchro (J-14, expiré…) | doc 12 §1.2, doc 16 |
| #7 | Journal d'audit append-only des décisions et signatures | doc 12 §1.1 |
| #8 | Décisions et signatures verrouillées en base | doc 12 §1.3 |
| #9 | Contre-passation d'une transaction modifiée ou supprimée après comptabilisation | doc 06, doc 16 |
| #10 | Documentation de #7 à #9 | doc 18 |

Conséquence pour la démo : une base amorcée avant ce jour doit passer
`alembic upgrade head` (trois migrations de plus : `b7e2d4a81c06`,
`c2f91ab84e30`, `d8b41c6e0a27`). Le seed lui-même ne change pas.

Revue Bugbot de la PR de rattrapage (#11), trois bugs réels corrigés
avant le merge. Une contre-passation passait par le 471 et revenait donc
dans la file « à trancher », sans suivre la décision de son originale (la
paire ne s'annulait plus dans la liasse). Une ligne bancaire revenue à
l'identique après contre-passation passait pour « déjà connue » alors
qu'elle n'était plus comptabilisée. Et la réponse de l'ajout de
justificatif remettait une ligne annulée en « à trancher ». Helpers `origine`/`annulees` dans
`ledger/contrepassation.py`.

Incident de process, corrigé le même jour : les PR #6 à #10 étaient
empilées (chacune basée sur la précédente) et ont été mergées dans leur
branche parente après que #5 était déjà partie dans `main`. Elles
apparaissaient « merged » sur GitHub sans être dans `main`. Rattrapé par une
PR unique vers `main`. Pour une prochaine pile : merger du haut vers le bas,
ou rebaser chaque PR sur `main` avant de merger sa base.

