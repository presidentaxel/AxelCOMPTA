# Archive — doc 18, « Statut d'implémentation actuel »

> Copie telle quelle de la section retirée du doc 18 le 2026-09-25. Historique,
> ne plus mettre à jour : l'état courant est dans le doc 12.

## Statut d'implémentation (au 2026-09-25)

**Semaines 0 à 3 du doc 17 faites (2026-09-05)** :
- Semaine 0 : `python -m axelcompta.demo` produit un vrai PDF, en mémoire
  (`InMemoryLedgerService`, pas de DB requise). Postgres + Alembic sont
  montés (`docker-compose.yml`, `migrations/`) et vérifiés contre un vrai
  conteneur (`PostgresLedgerService`, tests d'intégration) mais pas encore
  branchés dans `demo.py`.
- Semaine 1 : les 5 providers rendent des données (plus aucun
  `NotImplementedError`). `FileImportProvider` (chemin C) rejoue le vrai CSV
  audit (36 152 lignes) — testé contre le fichier réel. `DigifactoryProvider`/
  `RolleeProvider` restent chemin B (fixtures) : token 401 et sandbox non
  vérifié toujours d'actualité côté Louis, chemin A non tenté.
- Semaine 2 : `reconcilier()` (doc 13 §4.2, montant ±1cts/fenêtre de
  date/libellé) remplace le bouchon. `construire_ecriture_settlement`
  (doc 13 §5.3) reproduit le golden test Uber exactement et gère le cas
  Bolt (autoliquidation). `RulesAndMlPipeline` (règles du pack + modèle
  `tfidf_logreg_v1.joblib` chargé comme artefact) catégorise le reste des
  transactions ; `workflow/auto_accept.py` les transforme en écriture sans
  revue humaine (stand-in assumé, pas l'architecture cible).
- Semaine 3 : `ClotureSimplifieeService` (`closing/bilan_simplifie.py`)
  remplace le bouchon — compte de résultat + bilan qui s'équilibrent
  réellement (trésorerie = résultat + TVA à payer, vérifié en test).
  `PdfLiasseSimplifieeRenderer` (`filings/liasse_simplifiee.py`) remplace le
  dump brut de comptes par une présentation compte de résultat/bilan/case
  2065 — toujours pas conforme CERFA/DGFiP, écrit noir sur blanc dans le PDF.
- Hors plan initial, demandé explicitement (2026-09-05) : `PdfCerfa2065Renderer`
  (`filings/cerfa_2065.py`) fait un overlay sur le **vrai formulaire
  officiel** 2065-SD (téléchargé depuis impots.gouv.fr, ADR-006 mis à
  jour). Une seule case remplie (résultat fiscal), le reste blanc car hors
  profil démo. Nuance importante : ceci reste de la fidélité visuelle pour
  la relecture humaine, **pas une conformité légale** — le dépôt réel du
  2065 est obligatoirement télétransmis par EDI/EFI (doc 02, statut
  Partenaire EDI), jamais par PDF.
- `backend/axelcompta/demo_dossier_reel.py` (2026-09-05, doc 17 §7bis) :
  composition root sœur de `demo.py`, tourne sur un vrai dossier complet
  (543 transactions réelles, résultat négatif) plutôt qu'un exemple à 2-3
  lignes — a fait remonter un vrai bug de mapping compte-par-catégorie
  (`recettes_plateformes`), corrigé dans `packs/vtc_demo.py`.
- Semaine 4 (2026-09-05) : `demo_multi_dossiers.py` tourne sur **3 vrais
  dossiers** (pas des fixtures) et génère un rapport HTML (doc 17 §6) avec,
  pour chacun, liasse + CERFA 2065 + FEC + grand livre + balance. A fait
  remonter un **deuxième** vrai bug, plus large que le premier : 11 des 12
  règles regex du pack n'étaient pas insensibles à la casse — le CA détecté
  d'un dossier est passé de 591 € à 11 937 € une fois corrigé
  (`re.IGNORECASE` forcé dans `charger_regles()`).
- Demandé explicitement, hors plan initial (2026-09-05) : `filings/fec.py`
  (export FEC, 18 colonnes normées, doc 06 §6) et
  `filings/export_comptable.py` (grand livre, balance) — le détail légal et
  comptable derrière les chiffres de la liasse, pour un contrôle fiscal ou
  pour tracer une erreur.
- 2026-09-23 (doc 17 §15) : clôture fiscale complète dans `closing/`
  (`cloture_fiscale.py` orchestre `ecritures_cloture.py`, `impot_societes.py`,
  `liasse_2033.py`, `liasse_2033_annexes.py`, `rubriques_2033.py`) et liasse
  officielle dans `filings/` (`cerfa_2033.py`, `cerfa_2065.py` complété,
  `liasse_fiscale.py`, `overlay_cerfa.py`). Les coordonnées des cases du
  2033 sont extraites du PDF officiel par `backend/scripts/extraire_cases_cerfa.py`
  vers `filings/cerfa/cases_2033-sd_2026.json`. `fec.py` suit désormais
  l'article A.47 A-1 à la lettre. Identité légale : `core/identite.py`,
  persistée par `tenants/identite_json.py`.

Détail et commandes : [backend/README.md](../../backend/README.md).

Doc 17 semaines 0 à 4 (version backend-first) sont toutes faites — ce
travail reste la brique de calcul réutilisée telle quelle. **Pivot du
2026-09-06** : doc 17 est réécrit pour une démo produit avec deux
interfaces (gestionnaire PC, chauffeur mobile), parcours cadré dans
[doc 19](../19-parcours-utilisateur.md) (doc 12 §2.7). Aucun code front
n'existe encore pour ces deux interfaces — c'est l'objet du nouveau plan.

**Semaine 1 du nouveau plan faite (2026-09-06)** : jeu de données des 3
chauffeurs type (`ingestion/providers/chauffeurs_demo.py`,
`demo_chauffeurs_type.py`, doc 17 §4/§9) — génération déterministe, aucun
fichier gitignored requis contrairement à `demo_dossier_reel.py`/
`demo_multi_dossiers.py`. A fait remonter deux écarts dans le moteur
existant, corrigés : `ingestion/ecritures_settlement.py` n'avait pas de
régime franchise (`tva_recettes_regime` était figé en dur à 10% assujetti,
profil unique de l'ancien plan) ; le pack réduit n'avait pas de règle pour
le financement en LOA (ajoutée dans `_AUDIT_DONNEES/packs_vtc/regles_regex.csv`).
Les deux corrections sont des extensions du moteur, pas des contournements —
testées (`tests/ingestion/test_ecritures_settlement.py`,
`tests/ingestion/providers/test_chauffeurs_demo.py`), inchangées pour les
dossiers existants (comportement par défaut identique).

**Rattrapage (2026-09-09) : les blocs A/B/C de la Semaine 2 (doc 17 §9,
faits entre le 2026-09-06 et le 2026-09-08) manquaient ici — ce doc
s'était arrêté à la Semaine 1 alors que trois jours de travail supplémentaires
avaient déjà eu lieu.** Détail complet dans doc 17 §9 ; ce qui change pour
la correspondance code ↔ modules :

- **`workflow/`** passe de « non prévu démo » à **actif démo** :
  `decisions.py` (`DecisionHumaine` immuable + `AnnotationDev`),
  `decisions_memory.py`/`decisions_postgres.py`/`orm.py` (persistance
  réelle Postgres, migration `55cf8c93e5bf`, doc 17 §9 bloc A) et
  `revue.py` (reclassification 471 → compte réel, bloc C). `auto_accept.py`
  reste en place comme fallback (doc 17 §5), plus comme unique chemin.
- **Comptes et auth** : `demo_comptes.py`/`demo_comptes_memory.py`
  (invitation gestionnaire → chauffeur via Supabase Auth) et
  `demo_auth.py` (vérification des jetons chauffeur, JWKS/ES256) —
  **composition roots de démo**, comme `demo_api.py` et
  `demo_chauffeurs_type.py`, donc délibérément **hors** du découpage
  doc 03 §3 et de son graphe de dépendances : `tenants`/`api` restent le
  point d'entrée V1 pour les vrais comptes (toujours via Supabase, doc
  ADR-003 mis à jour le 2026-09-08), pas ces fichiers de démo.
- **`demo_api.py`** gagne `POST /dossiers/{id}/transactions/{ecriture_id}/decision`
  (bloc C) et `POST /dossiers/{id}/inviter` (bloc B) — toujours une
  composition root distincte de `axelcompta/api/` (`app.py`, 15 lignes,
  toujours un squelette, inchangé par ce lot).
- **`frontend/`** gagne `TrancherActions.tsx` (bouton de revue), 
  `InvitationActions.tsx` (invitation), et le groupe de routes
  `app/chauffeur/*` + `lib/auth-chauffeur.ts` (connexion chauffeur,
  appels REST directs à Supabase Auth, jamais le SDK JS — même règle
  qu'côté backend).

**Rattrapage (2026-09-09) : Semaine 3 (doc 17 §9) faite** — parcours
mobile chauffeur complet (question de catégorisation, photo de
justificatif, signature mockée), voir doc 17 §9 pour le détail. À cette
occasion, `_trancher()` a été ouvert au chauffeur authentifié (plus
seulement gestionnaire) : `UTILISATEUR_DEMO` reste en dur uniquement
pour le chemin gestionnaire (sans login **à cette date ; remplacé le
2026-09-21**, voir plus bas), pas pour le chauffeur
qui est maintenant identifié par son vrai `user_id` Supabase.
`demo_justificatifs.py` (nouveau, composition root de démo) tient le
même rôle que `demo_comptes.py`/`demo_auth.py` — hors doc 03 §3.

**Semaine 4 (doc 17 §9), partiellement faite le 2026-09-11** : clôture/
liasse exposées dans l'UI gestionnaire — 5 routes de téléchargement dans
`demo_api.py` (liasse/CERFA 2065/FEC/grand livre/balance, sur le ledger
avec décisions humaines appliquées, pas le ledger brut) et
`frontend/components/ClotureSection.tsx` (compte de résultat + bilan
simplifié + liens de téléchargement) sur la fiche dossier. Digifactory
étant débloqué le même jour (doc 16), `DigifactoryHttpClient` (chemin A,
vrais appels HTTP) rejoint aussi `ingestion/providers/digifactory.py` —
toujours pas branché sur `fetch_transactions` (mapping `contact_nr →
dossier_id` manquant, doc 16 §9 point 5).

**Dossier greffe/INPI fait le même jour (doc 20, doc 17 §9)** :
`filings/inpi_depot.py` (`construire_payload_comptes_annuels` — vraie
forme de l'API INPI ; `PdfDepotInpiRenderer`, stand-in démo marqué
FICTIF) et un nouveau module `workflow/signature.py`
(`SignatureProvider`/`DocumentSigne`/`SignatureRepository`, l'abstraction
pour le futur prestataire réel, comparatif doc 20 §6) +
`signature_demo.py`/`signature_memory.py`. `workflow` passe ainsi de
« Réduit démo (auto-accept, pas de revue) » à couvrir aussi la signature,
comme annoncé de longue date dans le tableau ci-dessus (« Validation,
revue, signature électronique »). `demo_api.py` gagne les routes
`GET/POST .../greffe-inpi{.pdf,/signature}` ; `frontend/components/GreffeInpiSection.tsx`
sur la fiche dossier.

**Déplacé le 2026-09-11, même jour** (doc 19 §8) : `ClotureSection.tsx`
et `GreffeInpiSection.tsx` vivent maintenant sur `frontend/app/chauffeur/[dossierId]`,
plus sur la fiche dossier gestionnaire (supprimée, ainsi que
`TrancherActions.tsx`) — le gestionnaire n'a plus qu'un dashboard agrégé
(`app/(gestionnaire)/page.tsx`, cartes sans navigation). Signature
authentifiée via `signerGreffeInpiChauffeur` (`lib/auth-chauffeur.ts`), pas
la version anonyme de `lib/api.ts` (retirée). Le code backend (`filings/`,
`workflow/signature.py`) n'a pas bougé, toujours correct tel quel —
`workflow/signature.py` modélise une seule étape de signature ; le vrai
parcours en a deux (doc 20 §4bis, validation + légale) — à étendre, pas à
réécrire.

**Jeton obligatoire + append-only, même jour (doc 19 §8bis)** : les routes
indiv de `demo_api.py` exigent désormais un jeton valide (401 sinon), le
stub `UTILISATEUR_DEMO` est retiré, et `workflow/signature_memory.py` garde
l'historique complet des signatures (`lister()`) au lieu d'écraser la
précédente — condition pour que ça vaille comme preuve.

**Auth gestionnaire faite (2026-09-21)** : `demo_auth.py` lit le lien
`tenant_id` dans `app_metadata` (jamais `user_metadata`, modifiable par
l'utilisateur) en plus de `dossier_id`. `GET /dossiers` et
`POST /dossiers/{id}/inviter` exigent ce lien (avant : routes ouvertes, la
liste exposait CA/résultat/trésorerie des dossiers à n'importe qui).
`/dossiers` renvoie `DossierAgregat`, modèle distinct de `DossierResume` :
plus de nombre de transactions, trésorerie, TVA ni statut de signature
greffe (doc 19 §2.4). Frontend : `/connexion`, `lib/auth-gestionnaire.ts`,
dashboard en composant client. Création du compte : 
`backend/scripts/creer_compte_gestionnaire.py` (clé service role, non lancé
depuis ce dépôt). (Les deux restes de ce paragraphe, `dossier_id` dans `user_metadata` et le
tenant en constante, sont traités dans le paragraphe suivant.)

**Postgres branché (2026-09-21)** : `demo_api.py` ne recalcule plus rien à
la volée. Dossiers et tenants (`tenants/`, `DossierRepository`, tables
`tenants` et `dossiers` étendue), ledger (`PostgresLedgerService`) et
propositions d'origine du pipeline (`workflow/propositions*.py`, table
`propositions_categorisation`) sont lus en base ; les décisions humaines
restent une couche séparée appliquée par-dessus (append-only). L'appartenance
d'un dossier à un portefeuille vient de `dossiers.tenant_id` (plus de
constante). `python -m axelcompta.demo_seed` amorce la base depuis les
profils de démo, et sera le point d'entrée des dossiers réels (Digifactory).
`dossiers.contact_nr` (unique) est la table de correspondance
`contact_nr -> dossier_id` qui bloquait le branchement de Digifactory (doc 16
§9 point 5). Migration `614c1b3e65e8`, round-trip vérifié. Deux détails :
les ids d'écritures sont préfixés par le dossier à l'amorçage (le pipeline les
numérote par dossier, ils entraient en collision sur la clé primaire), et le
lien chauffeur -> dossier est passé dans `app_metadata` (le `dossier_id` de
`user_metadata` était modifiable par le chauffeur lui-même).

**Synchro Digifactory (2026-09-22)** : `python -m axelcompta.synchro_digifactory
--tenant X` lit chaque dossier du portefeuille via son `contact_nr`
(`DigifactoryProvider.lire_lot`), archive tout le brut (`ingestion_brut`,
insert-only, clé = empreinte du contenu), catégorise, écrit
proposition puis écriture, et avance le curseur (`curseurs_synchro`) en
dernier. Idempotent : l'id d'écriture dérive de l'id de transaction
(`{dossier}:digifactory-{id}`), plus d'un compteur. Le ledger reste
append-only : une transaction modifiée ou supprimée après comptabilisation
est contre-passée et part en `quarantaine_ingestion` (précisé le
2026-09-24, paragraphe suivant). Politique
d'acceptation automatique **provisoire** (`workflow/synchro.py`) : règle
haute/moyenne confiance ≥ 0,75, ML ≥ 0,90, sinon compte 471 donc file de
revue de l'indiv ; les virements Uber/Bolt vont toujours en 471 tant qu'aucun
settlement (Rollee) ne les réconcilie, jamais en 706 sans ventilation TVA.
Migration `a016d1659a6e`. Pas de planificateur : cron ou lancement manuel
tant que la file de jobs n'existe pas.

**Verrous, journal, consentement, contre-passation (2026-09-24)** :
- Migration `a91c4e2b7d10` : `UPDATE` et `DELETE` refusés sur `ecritures`
  et `lignes_ecriture` (`axelcompta_interdire_mutation()`). Le propriétaire
  de la base est soumis au trigger, comme le rôle web.
- `ingestion/consentement.py` + table `consentements_bancaires` (migration
  `b7e2d4a81c06`) : à chaque synchro, le statut DSP2 est classé
  (`actif` / `a_renouveler` à J-14 / `expire` / `jamais_connecte`) depuis
  `item.authentication_expires_at` et enregistré. Pas d'e-mail, pas
  d'écran : le dashboard et les relances de doc 14 §2.2-2.3 restent à faire.
  La table est l'état courant (mise à jour autorisée), pas une écriture.
- `workflow/audit.py`, table `journal_audit` (migration `c2f91ab84e30`) :
  chaque décision et chaque signature écrivent une ligne dans la même
  transaction (dossier, type d'acte, référence, acteur, horodatage). Pas
  de libellé bancaire, pas de PDF. Le journal « qui a consulté / exporté »
  de doc 10 n'est pas couvert.
- Migration `d8b41c6e0a27` : le même trigger sur `decisions_humaines` et
  `documents_signes`. Une correction est une nouvelle ligne.
- `ledger/contrepassation.py`, appelée par `workflow/synchro.py` : une
  transaction déjà comptabilisée que Digifactory modifie ou supprime
  reçoit une écriture inverse (journal OD, mêmes montants, sens opposés,
  id `{écriture}:contrepassation`, une seule fois). L'originale ne change
  pas et le nouveau montant n'est pas comptabilisé tout seul. La
  quarantaine reste posée. Pas de migration : aucun changement de schéma.

**Synchro Digifactory durcie (2026-09-25)** : sans curseur, le premier
chargement est découpé mois par mois (`from`/`to`, de l'exercice à
aujourd'hui) ; le suivant reste sur `since`. Une réponse vide est un succès
à zéro ligne. Un dossier en 401 n'arrête pas les autres. La lecture des
comptes enregistre aussi la santé de connexion sur `consentements_bancaires`
(migration `a3e8c1d94f20`). Pas d'écran.

**Clés étrangères, notifications, invitations en masse (2026-09-22)** :
- Migration `7cd5053e8209` : FK des décisions, annotations, propositions et
  tables du journal d'ingestion vers `dossiers` (et `ecritures` pour les
  décisions et annotations). `propositions_categorisation.ecriture_id` n'en a
  pas, volontairement : la synchro écrit la proposition avant l'écriture.
- `workflow/notifications.py`, `emails.py` (interface + SMTP standard, sans
  SDK propriétaire) et `python -m axelcompta.notifier --tenant X
  [--simulation]` : e-mail « opérations à confirmer » regroupé par dossier,
  anti-harcèlement (nouvelles opérations et 6 h d'écart, ou rappel à 7 jours),
  aucun montant dans le message, envoi enregistré seulement s'il a réussi,
  seuls les comptes **activés** sont notifiés. Table `notifications_envoyees`
  (migration `ca7b37bba581`). Pas de planificateur : cron après la synchro.
- `POST /invitations/en-masse` et écran gestionnaire correspondant.
  **Bug corrigé au passage** : `GET /admin/users` de Supabase est paginé (50
  par page) et n'était lu qu'en première page ; au-delà de 50 comptes, un
  dossier déjà invité recevait une seconde invitation. Lecture paginée, et
  `statuts()` lit les comptes une seule fois pour tout un lot.

**Pas encore fait, donc pas dans l'arbre ci-dessus** : écran `chauffeur_direct` de connexion
bancaire réelle (aujourd'hui un bouton désactivé, stub visuel), appel réel
à l'API INPI (bloqué sur ADR-004, pas un problème de schéma, doc 20 §5),
répétition avec run pré-cuit.

**RLS Postgres posée (2026-09-22, doc 03 §7, doc 12 §1.1)** : nouveau
`axelcompta/core/rls.py` (contexte par requête via `ContextVar`,
`set_config(..., true)` — portée transaction, jamais fuité entre deux
requêtes qui réutiliseraient la même connexion du pool). Migration
`87fc7238e52e` : rôle `axelcompta_web` (ni propriétaire ni superuser,
utilisé uniquement par `demo_api.py` via `DATABASE_URL_WEB`), policies sur
les 11 tables dossier/tenant-scopées, fonction `axelcompta_dossier_visible`
partagée entre policies. `user` (migrations, `demo_seed`,
`synchro_digifactory`, `notifier`, `DATABASE_URL`) reste propriétaire,
jamais soumis — ces scripts traitent volontairement plusieurs dossiers à
la fois. Les 6 repositories Postgres appellent `appliquer_rls(connexion)`
en tout premier dans chaque transaction. Middleware `demo_api.py`
(`_configurer_contexte_rls`) plutôt qu'une dépendance FastAPI classique :
l'ordre de résolution des dépendances n'est pas une garantie assez forte
pour un mécanisme de sécurité. `demo_auth.identite_tolerante` (nouveau) —
jamais de levée, la décision d'autoriser reste entièrement dans
`_verifier_acces_dossier`. 7 tests dédiés
(`tests/integration/test_rls_isolation.py`), dont un qui vérifie que le
`WITH CHECK` bloque aussi l'écriture (pas seulement la lecture). **Piège
trouvé en testant** : `DROP ROLE` est une opération de *cluster* Postgres,
pas de base — `axelcompta_test` et `axelcompta_dev` partagent le même
cluster, la migration ne supprime donc jamais le rôle en downgrade
(`DependentObjectsStillExist` sinon), seulement ses droits/policies sur la
base courante.

**Comptes de démo + re-vérification backend (2026-09-22)**, suite au
branchement Postgres/auth du 21-22/09 qui n'avait pas été retesté depuis :
`backend/scripts/creer_comptes_demo_chauffeurs.py` (nouveau, même style que
`creer_compte_gestionnaire.py`) crée les 3 comptes chauffeur de démo avec
`app_metadata.dossier_id` seul (pas de `tenant_id` — jamais d'accès
portefeuille pour un chauffeur) et `app_metadata.env: "demo"` pour les
distinguer plus tard de vrais comptes pilote. Deux comptes gestionnaire
créés aussi (`louis.vedovato@axelproject.fr`, `demo@axelcompta.fr`) — les
5 comptes sont persistants cette fois, pas supprimés après vérification
comme les comptes de test des sessions précédentes. Backend re-testé en
réel avec ces comptes (login Supabase, dashboard agrégé, 401/403,
tranchage 471→455 vérifié dans le FEC, téléchargement liasse, signature
greffe/INPI avec PDF qui change) — détail complet doc 17 (Semaine 4,
paragraphe daté 2026-09-22). **Non vérifié** : le rendu front — `node`/`npm`
absents de l'environnement Claude Code utilisé, `next dev` pas lancé.
