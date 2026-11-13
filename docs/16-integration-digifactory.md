# 16 — Intégration Digifactory (source bancaire)

> **État au 2026-11-13** (ajouté) : synchro réelle codée (curseur, archive
> brute, quarantaine, contre-passation), premier chargement découpé et
> santé de connexion relevée (AXE-443). Mode réel depuis le 05/11 (doc
> 17) : seuls les contacts listés sont importés (AXE-726), dossiers pilotes
> des vrais chauffeurs (AXE-727). Depuis : chaque compte bancaire est
> retenu, écarté ou à décider, et la synchro écarte les opérations d'un
> compte non retenu (AXE-729, AXE-851) ; un sous-compte 512x par compte
> (AXE-832) ; les nouveaux contacts sont proposés dans Entreprises et le
> bouton « Synchroniser » passe par le worker (AXE-845) ; la quarantaine
> se résout depuis Anomalies (AXE-424). Depuis le 12/11 (AXE-872), le jeton
> Digifactory est un branchement du portefeuille, chiffré, et il peut y en
> avoir plusieurs : la synchro ouvre un client par jeton, les nouveaux
> contacts sont lus sur chaque compte. `DIGIFACTORY_TOKEN` ne sert plus
> qu'en repli, tant qu'aucun branchement n'existe. Les IBAN des comptes
> servent aussi à relier les users Rollee (AXE-911, sous forme
> d'empreinte). Prochaine étape : la première synchro des chauffeurs réels
> (AXE-728), puis un mois exporté (AXE-733).

> **Statut : les 4 routes vérifiées en réel le 2026-09-11 — voir §7.** Le
> 401 n'était pas un problème côté Digifactory : c'était un mauvais type
> d'en-tête utilisé côté client depuis le début (§2). Chemin A implémenté
> (`DigifactoryHttpClient`, `backend/axelcompta/ingestion/providers/digifactory.py`)
> et testé contre la vraie API, pas seulement contre des fixtures.
> Dernière mise à jour : 2026-09-11.

> **Phasage : Digifactory est le canal exclusif pour septembre 2026.**
> Bridge reste la source de données de base (Digifactory n'est qu'un tampon qui
> agrège les mêmes données Bridge par contact) — on ne retire rien de ce qui
> existe sur Bridge dans les autres docs. L'accès Bridge direct (sandbox, §8)
> est une piste parallèle non bloquante, testée après la période Digifactory,
> pas en concurrence avec elle. `DataProvider` (doc 13 §2) est conçu pour
> encaisser les deux sans changement ailleurs dans la chaîne d'ingestion.

---

## 1. Contexte et décision

L'accès aux données bancaires **ne se fait pas en direct auprès de Bridge**
pour le moment. Digifactory (contact : Pierre BERTOLA) est déjà client Bridge,
agrège les données par contact, et nous expose une API dédiée construite à
notre demande.

**Conséquences :**

- On implémente un `DigifactoryProvider`, pas un `BridgeProvider`, dans un
  premier temps. Le pattern DataProvider (doc 13 §2) absorbe le changement :
  rien d'autre ne bouge dans la chaîne d'ingestion. Un `BridgeProvider` direct
  reste prévu (§8) mais n'est pas développé tant que Digifactory couvre le
  besoin du pilote.
- Pas de webhook. Le rafraîchissement est en **pull**, à notre initiative.
- Digifactory ne peut pas nous fournir de credentials Bridge : leur plateforme
  n'expose qu'un seul couple `client_id`/`client_secret`, utilisé par leur
  propre application. Un accès Bridge direct, s'il est ouvert un jour, passera
  par une application séparée (voir §8).
- L'identifiant pivot pour le canal Digifactory est le **`nr` de contact
  Digifactory**, distinct du `bridge_item_id` déjà présent dans le CSV
  d'onboarding (doc 14 §1.2). Les deux colonnes coexistent : `bridge_item_id`
  reste réservé au jour où le provider Bridge direct sera actif.

---

## 2. Accès

**Base URL :** `https://entrepreneur.digifactory.fr/api/bridge`

**Authentification : en-tête `X_DIGI_TOKEN: <token>` — ce n'est PAS un
bearer token.** Corrigé le 2026-09-11 (Pierre BERTOLA) : Digifactory a deux
types de token, et la spec initiale (`Authorization: Bearer <token>`) nous
avait été donnée pour l'autre type par erreur. C'est la cause réelle du 401
qui bloquait depuis le 2026-09-01 — rien n'était cassé ni de notre côté
(client) ni du côté Digifactory, juste un mauvais nom/format d'en-tête.
**Confirmé par appel réel le 2026-09-11** (§7) : `X_DIGI_TOKEN` fonctionne,
`Authorization: Bearer` ne fonctionnera jamais pour ce type de token — ne
pas revenir dessus si un futur doute survient.

Le token est un secret de 64 caractères (shared secret, pas un JWT/bearer),
transmis hors bande. Il ne doit jamais être commité ni écrit dans un fichier
versionné — lecture par variable d'environnement uniquement
(`DIGIFACTORY_TOKEN`).

Cycle de vie du token (durée de validité, rotation, scope, procédure en cas de
fuite) : **non documenté**, question posée au fournisseur, sans réponse à ce
jour. Traiter comme révocable à tout moment : l'échec d'authentification doit
être un cas géré explicitement, pas une exception qui remonte brute.

---

## 3. Routes

Les quatre routes fournies, telles que communiquées :

```
GET /contacts
GET /accounts/{contactNr}
GET /transactions/{contactNr}
GET /categories
```

Toutes en `GET`, avec l'en-tête `accept: */*`.

### 3.1 `/transactions/{contactNr}`

**Paramètres :**

| Paramètre | Format | Usage |
|---|---|---|
| `since` | `YYYY-MM-DD HH:MM:SS` | Filtre sur `updated_at`. **À utiliser pour tout sync courant.** |
| `from` / `to` | `YYYY-MM-DD HH:MM:SS` | Filtre sur la date d'opération. Rattrapages ponctuels uniquement. |

**`since` est le mode nominal.** Il a été demandé et implémenté spécifiquement
parce que `from`/`to` filtrent sur la date de transaction : une opération du 3
corrigée par la banque le 12 (pending → booked, montant ajusté, suppression)
n'apparaîtrait jamais dans une fenêtre glissante sur la date d'opération. Le
sync incrémental doit donc s'appuyer sur `since`, en persistant le `updated_at`
max observé au dernier passage.

**Forme de la réponse :** objet indexé par `accountId`.

```json
{
  "<accountId>": { "<transactionId>": { ...transaction }, ... },
  "<accountId>": { ... }
}
```

**Vérifié par appel réel le 2026-09-11** (§7, 2 contacts, 2029 transactions
au total) : l'indexation est bien par `accountId`, comme corrigé par Pierre.
**Écart réel trouvé, différent de ce qui était documenté avant cette
session** : chaque compte n'est **pas une liste** de transactions mais un
**dict `{transactionId: transaction}`**. `parser_transactions` (code) est
corrigé en conséquence (`_transactions_de_compte`, accepte les deux formes)
— ce n'était pas qu'une note de doc, ça aurait fait planter le parsing du
premier vrai payload tel qu'écrit avant aujourd'hui (`for tx in
transactions` itérait sur les clés du dict, pas sur les transactions).

Le parsing doit néanmoins **ne pas dépendre de la clé du niveau compte** —
lire `account_id` sur chaque transaction si le champ y est présent, et ne
se rabattre sur la clé que sinon (déjà le cas, `parser_transactions`
inchangé sur ce point).

### 3.2 `/accounts/{contactNr}`

Réponse indexée par identifiant de compte. Champs annoncés :

```
id  name  item_id  provider_id  pro  data_access  paused  iban
balance  type  currency_code  updated_at  last_refresh_status
```

**Vérifié par appel réel le 2026-09-11** (2 contacts, 13 comptes au total) :
tous ces champs sont bien présents, sans exception. Précisions réelles,
absentes de la description initiale du fournisseur :
- **Un contact sans compte connecté renvoie `[]`** (liste vide), pas `{}`
  — le type de la réponse n'est donc pas toujours un objet, à gérer
  explicitement (`DigifactoryHttpClient.accounts` typé en conséquence).
- `last_refresh_status` observé toujours à la valeur sentinelle
  `"0000-00-00 00:00:00"` (format date zéro façon MySQL) sur tous les
  comptes de l'échantillon, jamais un vrai timestamp ni `null` — à traiter
  comme une valeur non renseignée, pas comme une date réelle à parser.
- `item` (objet lié) contient bien plus que « dates de rafraîchissement » :
  `id`, `provider_id`, **`provider`** (imbriqué *dans* `item`, pas un objet
  frère comme la phrase initiale pouvait le laisser penser — voir
  ci-dessous), `status` (entier), `status_code_info` (chaîne, ex. observées :
  `"ok"` et `"sca_required_webview"` — ce dernier signifie une connexion qui
  demande une nouvelle authentification forte, un vrai cas de « connexion
  cassée » à distinguer d'un compte simplement inactif, doc 16 §5
  « Santé de connexion »), `account_types`, `paused`, `last_successful_refresh`,
  `last_try_refresh`, `created_at`, et **`authentication_expires_at`** —
  qui répond enfin à la question ouverte du §6 : **oui, la date d'expiration
  du consentement DSP2 est exposée**, format `YYYY-MM-DD HH:MM:SS`, observée
  jusqu'à ~3 mois dans le futur sur les comptes actifs de l'échantillon.
- `item.provider` (imbriqué) : `id`, `name` (nom de la banque, ex. observés :
  Bunq, Swan), `country_code`, `group_name`, `logo` (URL), `health_status`
  (ex. observé : `"healthy"`).

Aucune IBAN/nom de compte réel reproduit ici — champs et formes uniquement,
pas de vraies données clients dans ce fichier (cf. §3.3).

### 3.3 `/contacts`

Liste des contacts. Le champ `nr` est l'identifiant pivot.

**Vérifié par appel réel le 2026-09-11** (§7) : réponse = objet indexé par
`nr` (pas un tableau), champs constants par contact : `nr`, `firstname`,
`lastname`, `companyNr`, `companyName`.

**Écart du même jour expliqué et corrigé côté fournisseur (même jour,
Pierre BERTOLA), reste noté ici pour l'historique et pour qui retombe sur
une ancienne capture** : le premier appel du 2026-09-11 renvoyait un champ
unique `siret` contenant en fait soit un SIREN (9 chiffres) soit un SIRET
(14 chiffres) selon ce qui est saisi côté fiche société Digifactory — **ce
n'était pas un bug, c'est le fonctionnement normal de leur champ interne**
(usage double assumé par Digifactory). Corrigé à notre demande : Pierre a
scindé ça en deux champs distincts, plus un troisième ajouté en bonus.
**Retesté en réel le 2026-09-11 (même jour, après son mail)** — champs
optionnels désormais :
- `siren` (9 chiffres) — présent sur l'échantillon quand la fiche société
  a un SIREN saisi.
- `siret` (14 chiffres attendus — ⚠️ pas encore observé dans l'échantillon,
  aucun des 5 contacts de test n'avait cette variante renseignée).
- `vatno` — numéro de TVA intracommunautaire, présent seulement s'il est
  renseigné côté Digifactory. Format observé : `FR` + 11 caractères (13 au
  total), cohérent avec le format standard FR.
- Un contact de l'échantillon n'a **aucun** des trois (ni `siren`, ni
  `siret`, ni `vatno`) — confirme qu'il faut garder le mapping
  `nr → dossier_id` en table de correspondance explicite, pas une
  jointure automatique sur ces champs (toujours valable).

Le point de jointure attendu (SIREN/SIRET) est donc bien exploitable, à
condition de tester la présence de `siren` puis `siret` (pas juste l'un
des deux) lors du mapping `nr → dossier_id` (doc 16 §9 point 5).

Pas de données réelles de contacts reproduites ici (noms/SIREN/SIRET/TVA
de tiers) — si besoin de rejouer cet appel, relancer le curl (§7) plutôt
que de committer une capture.

### 3.4 `/categories`

Référentiel de catégories Bridge (Digifactory se contente de le relayer).

**À traiter comme une feature d'entrée du modèle de catégorisation, jamais
comme une vérité comptable.** Un `category_id` Bridge ne détermine pas un compte
du PCG. Il alimente le classifieur au même titre que le libellé ; il ne
court-circuite ni les règles ni la validation humaine.

---

## 4. Schéma transaction

Champs confirmés disponibles par le fournisseur (nomenclature Bridge) :

| Champ | Rôle | Criticité |
|---|---|---|
| `id` | Clé de déduplication | **Bloquant** |
| `provider_description` | Libellé brut de la banque | **Bloquant** — matière première de la catégorisation |
| `clean_description` | Libellé normalisé Bridge | Complément, ne remplace pas le brut |
| `amount` | Montant | **Bloquant** |
| `currency_code` | Devise | Requis |
| `date` | Date d'opération | Requis |
| `booking_date` / `transaction_date` / `value_date` | Dates détaillées | Selon disponibilité |
| `updated_at` | Sync incrémental | **Bloquant** |
| `deleted` | Transaction annulée | Requis — ne jamais comptabiliser |
| `future` | Transaction projetée | Requis — ne jamais comptabiliser |
| `operation_type` | Type d'opération | Feature |
| `category_id` | Catégorie Bridge | Feature uniquement |
| `account_id` | Compte bancaire | **Bloquant** — rapprochement |

**Vérifié par appel réel le 2026-09-11** (2029 transactions, 2 contacts,
toutes chez des providers bancaires FR) :
- Les 15 champs ci-dessus sont bien tous présents sur chaque transaction.
- `booking_date`/`transaction_date`/`value_date` : **toujours `null`** sur
  l'échantillon complet — jamais renseignés en pratique pour ces comptes.
  Ne pas construire de logique qui suppose leur présence ; `date` et
  `updated_at` restent les deux seuls champs de date fiables.
- `amount` : type JSON observé **int ou float** selon la transaction (un
  montant rond sérialise en int). `_vers_centimes` (code) passe déjà par
  `Decimal(str(montant))`, robuste aux deux — rien à changer.
- `currency_code` : toujours `"EUR"` sur l'échantillon (pas de multi-devise
  observée, mais l'échantillon ne le prouve pas pour tous les cas).
  `deleted`/`future` : toujours `false` sur cet échantillon — les cas vrais
  n'ont pas été observés en réel, seulement testés via fixtures (§7,
  couverts par les tests existants).
- `operation_type` : valeurs observées `card`, `unknown`, `direct_debit`,
  `transfer` — liste non garantie exhaustive.

---

## 5. Contraintes d'implémentation

**Montants.** Si `amount` arrive en float JSON, convertir en `Decimal` **dès le
parsing**, avant toute arithmétique. Jamais de float binaire sur de l'argent
(doc 08 §2, règle de lint bloquante). Le `Decimal` n'est qu'une étape
intermédiaire : la sortie du provider reste `NormalizedTransaction.montant_centimes`
(int, doc 04 §5), conforme au type `Money` du reste du système. Vérifier au
premier appel si l'unité source est l'euro ou le centime.

**Dates.** Le format annoncé (`YYYY-MM-DD HH:MM:SS`) est sans fuseau, et le
fournisseur a lui-même mentionné un décalage horaire. Normaliser en UTC à
l'ingestion, en documentant le fuseau source retenu. **Confirmé par appel
réel le 2026-09-11** : format bien `YYYY-MM-DD HH:MM:SS`, séparateur
espace (pas `T`), sans aucune information de fuseau dans la chaîne — le
décalage horaire mentionné par le fournisseur reste donc ⚠️ *à confirmer*
(quel fuseau source exactement), seul le format de sérialisation est
tranché. `datetime.fromisoformat` (Python ≥3.11) parse ce format
directement, y compris avec l'espace comme séparateur — pas besoin d'un
parseur dédié.

**Déduplication.** Clé = `id` de transaction. Un `id` déjà connu dont
l'`updated_at` a changé est une **mise à jour**, pas un doublon : il doit
déclencher la contre-passation de l'écriture associée (doc 06 I2,
`ledger/contrepassation.py`), pas être ignoré ni réécrit.

**Pagination.** Aucune pagination documentée sur ces routes. Le `since` borne le
volume en régime courant, mais le **premier appel sans filtre peut être
volumineux**. **Découpage fait le 2026-09-25** : sans curseur, `lire_lot`
appelle `from`/`to` mois par mois, de `exercice_debut` à aujourd'hui
(`fenetres_mensuelles`). Le passage suivant repart sur `since`. Les appels
restent en série.
**Mesuré en réel le 2026-09-11, sans filtre `since`** : un seul contact a
renvoyé ~807 Ko / 2029 transactions sur 4 comptes. Pas encore mesuré sur
l'historique complet des ~200 dossiers du pilote (dépend du nombre de
comptes et de l'ancienneté par chauffeur), mais confirme que l'appel
initial (sans `since`) doit être découpé plutôt que lancé tel quel sur
l'ensemble du pilote.

**Rate limit.** Non communiqué. Le fournisseur a explicitement demandé d'éviter
un volume de requêtes élevé et des réponses massives. Implémenter un backoff et
sérialiser les appels par défaut plutôt que de paralléliser.

**Santé de connexion.** La combinaison `paused` + `data_access` +
`status_code_info` distingue un chauffeur inactif d'une connexion cassée.
**Relevé fait le 2026-09-25**, dans la même lecture que le consentement
(`relever_sante`, colonnes sur `consentements_bancaires`) : `auth_requise`
(SCA) prime, puis `sans_acces`, puis `en_pause`, sinon `ok`. Le
rafraîchissement retenu est le plus ancien hors sentinelle `0000-00-00`.
Pas d'écran ni d'e-mail : le dashboard (doc 14 §2.2) lira cette ligne.

---

## 6. Ce qui reste ouvert

| Sujet | Impact |
|---|---|
| Profondeur d'historique conservée chez Digifactory | Détermine si la reprise d'antériorité passe par cette API ou uniquement par les FEC |
| ~~Date d'expiration du consentement DSP2 exposée ?~~ | **Résolu (2026-09-11)** : oui, `item.authentication_expires_at` sur `/accounts/{contactNr}` (§3.2). **Classement persisté le 2026-09-24** (`ingestion/consentement.py`, table `consentements_bancaires`) : `actif` / `a_renouveler` (≤ 14 jours) / `expire` / `jamais_connecte`, à chaque synchro. Le dashboard et les e-mails de relance (doc 14 §2.2-2.3) restent à faire. |
| Cycle de vie du token | Rotation, révocation, procédure d'incident |
| Chaîne de sous-traitance RGPD | chauffeur → Bridge → Digifactory → nous. Le consentement DSP2 signé couvre-t-il la retransmission ? Art. 28 à trois parties. **Non traité, à instruire en phase 0** (doc 02 §3, doc 10). |
| Qui gère le lien Bridge Connect pour un nouveau chauffeur | Digifactory possède la relation Bridge ; pas confirmé si l'ouverture d'une nouvelle connexion pour un chauffeur pilote passe par eux ou reste hors de notre contrôle (doc 14 §1.5). |

---

## 7. Statut du token — DÉBLOQUÉ le 2026-09-11

Le token reçu retourne un **401** sur `/contacts` :

```json
{"error":{"exception":"UnauthorizedException","code":401,
 "reason":"An authentication is mandatory for this action"}}
```

Écarté côté client : longueur correcte (64 caractères), aucun caractère
parasite, deux clients HTTP distincts, avec et sans préfixe `Bearer`. TLS et
routage fonctionnent — l'échec est bien au niveau de l'authentification côté
serveur. Signalé au fournisseur avec les tags de trace, en attente.

**En conséquence : développer contre des fixtures.** Le `DigifactoryProvider`
et ses tests peuvent être écrits intégralement contre le schéma ci-dessus.
Quand le token fonctionnera, les fixtures sont remplacées par des réponses
réelles capturées, et l'écart de schéma est traité à ce moment-là. Ne pas
attendre le déblocage pour commencer.

**Retest du 2026-09-07** : toujours 401, sur `/contacts` (avec et sans
préfixe `Bearer`) et sur `/categories`. Mêmes constats côté client
qu'au 01/09 (token correct, TLS/routage OK, échec au niveau
authentification serveur) — rien n'a changé en un mois. Document de
relance envoyé à Pierre BERTOLA avec tags de trace :
[archive/2026-09-07-relance-digifactory.md](archive/2026-09-07-relance-digifactory.md).

**Statut au 2026-09-08 : mail envoyé, en attente de réponse.** Pierre
BERTOLA est basé au Japon — décalage horaire important, délai de réponse
normal de quelques jours à compter de là, pas un signe que la relance s'est
perdue. Ne pas relancer une deuxième fois avant d'avoir laissé passer ce
délai.

**Réponse reçue (2026-09-09).** Pierre doit renvoyer des `curl` (à
confirmer lesquels — vraisemblablement des appels fonctionnels de son côté,
ou un jeton/une config à retester) **vendredi 2026-09-11**. Le token reste
401 jusque-là — rien à retester avant cette date. Session suivante :
vérifier si les curls sont arrivés et reprendre le retest de ce §7 à partir
d'eux.

**Cause réelle trouvée et corrigée (2026-09-11).** Pierre BERTOLA a
identifié l'erreur : Digifactory a deux types de token, et l'en-tête qui
nous avait été communiqué initialement (`Authorization: Bearer <token>`,
§2) était celui de l'*autre* type. Le nôtre est un shared secret, à passer
dans l'en-tête `X_DIGI_TOKEN`. Rien n'était cassé ni de notre côté ni de
celui de Digifactory pendant ces 10 jours — mauvaise spec dès le départ. Les
tags de trace du 2026-09-07 (relance) ne sont plus exploitables côté
Digifactory (délai de rétention des logs dépassé) — sans conséquence, la
cause est identifiée par un autre biais (Pierre a testé directement avec
notre token).

**Retesté et confirmé en réel le 2026-09-11**, avec le vrai token de
`.env` (`DIGIFACTORY_TOKEN`, suffixe `...8512`, celui transmis par Pierre) :

```
GET /contacts    → 200, objet indexé par nr, 5 contacts (voir §3.3)
GET /categories  → 200, arborescence de catégories Bridge (~60 entrées)
```

**`/accounts/{contactNr}` et `/transactions/{contactNr}` testés en réel le
2026-09-11**, avec validation explicite de Louis au préalable (données
bancaires réelles de tiers — contrairement à `/contacts`/`/categories` qui
n'exposent que de l'identité déjà communiquée par Pierre). 2 contacts, 13
comptes, 2029 transactions au total. Écarts trouvés reportés en §3.1
(forme dict, pas liste — bug potentiel évité), §3.2 (`authentication_expires_at`,
`status_code_info`, `[]` si aucun compte) et §4 (dates détaillées toujours
`null`, `amount` int ou float). **Aucune donnée réelle de contact, compte ou
transaction reproduite dans ce dépôt** — champs et formats uniquement ;
les captures brutes (utilisées le temps de cette session) n'ont pas été
committées.

**Chemin A implémenté et vérifié en réel** (pas juste en théorie) :
`DigifactoryHttpClient` (`backend/axelcompta/ingestion/providers/digifactory.py`)
— vrais appels HTTP avec le bon en-tête, testés contre `/contacts` et
`/categories` en conditions réelles (200, données réelles reçues, jamais
écrites sur disque dans le repo). `DigifactoryProvider.health()` fait
maintenant un vrai appel quand on lui fournit un `client_reel`. **Pas
encore fait** : brancher `fetch_transactions`/`fetch_platform_settlements`
sur le client réel — bloqué sur l'absence de la table `contact_nr →
dossier_id` (§9 point 5, ~200 chauffeurs), pas un problème technique : au
2026-09-26, Digifactory ne connaît que 6 contacts, les chauffeurs du pilote
n'y sont pas encore (doc 12, J3).

---

## 8. Accès Bridge direct (piste parallèle, non bloquante, après le pilote Digifactory)

Souhaité comme chemin de repli, pour ne pas dépendre d'un tiers unique sur une
brique aussi centrale que l'ingestion bancaire. Le fournisseur ne peut pas le
fournir et a raison de ne pas partager son secret de production.

Le chemin passe par une **application Bridge distincte** (chaque application a
son propre couple `client_id`/`client_secret`, aucune interférence avec la
production Digifactory), à ouvrir via l'équipe Bridge. Commencer par le
**sandbox**, qui débloque les spikes sans décision préalable. Ces tests
sandbox sont prévus **après** la période de test full-Digifactory de septembre
2026, pas en parallèle : Digifactory reste le seul canal actif ce mois-ci.

Point d'attention : le dashboard Bridge applique un **filtrage par IP**. Les IP
de sortie de la plateforme doivent être fixes et connues avant toute demande.

---

## 9. À faire côté code

1. ~~`DigifactoryProvider` implémentant l'interface `DataProvider`.~~ **Fait
   pour le chemin B (fixtures) depuis le début. Chemin A (vrais appels
   HTTP) fait le 2026-09-11** : `DigifactoryHttpClient`, testé en réel
   contre les 4 routes (§7). `DataProvider.fetch_transactions` n'utilise
   pas encore ce client réel (bloqué sur le point 5 ci-dessous).
2. Sync incrémental sur `since` : `DigifactoryHttpClient.transactions`
   accepte déjà `since` (2026-09-11) et le sérialise au bon format
   (`YYYY-MM-DD HH:MM:SS`, confirmé §5). **Curseur persisté depuis le
   2026-09-22** (`curseurs_synchro`, `ingestion/journal*.py`) : plus grand
   `updated_at` vu par (dossier, source), avancé en dernier et jamais
   reculé. La lecture recouvre la borne (inclusive, à confirmer côté
   fournisseur), sans effet car la synchro est idempotente.
3. Normalisation à l'ingestion : `Decimal` pour les montants — fait de
   longue date (`_vers_centimes`), confirmé robuste sur données réelles
   (§4, `amount` int ou float). UTC pour les dates — **pas fait**, le
   fuseau source exact reste ⚠️ à confirmer (§5).
4. Filtrage systématique de `deleted` et `future` — fait de longue date
   (`parser_transactions`), confirmé par tests, jamais observé en vrai sur
   l'échantillon testé (§4).
5. Table de correspondance `contact_nr → dossier_id` — **structure faite
   le 2026-09-22** (`dossiers.contact_nr`, unique, `DossierRepository.par_contact_nr`),
   et le chemin A est branché : `DigifactoryProvider.lire_lot(dossier, curseur)`
   appelle `/transactions/{contact_nr}` avec le contact du dossier, et
   refuse (`ContactNonMappeError`) un dossier sans contact plutôt que d'en
   deviner un. **Reste les données** : les ~200 chauffeurs du pilote
   doivent d'abord exister chez Digifactory (6 contacts au 2026-09-26).
   **2026-09-26/27** : les 6 contacts ont chacun un dossier de démo
   (`DIGI_<nr>`, `scripts/ajouter_chauffeurs_digifactory.py`, forme reprise
   de Sirene quand le contact a un SIREN ; SAS et SASU partagent le code
   5710, on ne devine pas). Deux ont des transactions. Constaté sur ces
   données : `operation_type` vaut `unknown` presque partout et
   `category_id` est le plus souvent générique ; ni l'un ni l'autre ne sert
   de feature au modèle aujourd'hui.
6. Monitoring de fraîcheur et de santé de connexion par compte — **relevé
   fait le 2026-09-25** (une ligne par dossier, le plus mauvais compte :
   `sante`, `en_pause`, `acces_donnees`, `dernier_rafraichissement`,
   migration `a3e8c1d94f20`). L'écran et l'alerte restent à faire (doc 14).
7. Fixtures et tests couvrant : transaction mise à jour rétroactivement,
   transaction supprimée, contact multi-comptes dans la même banque, connexion
   en échec, réponse vide — **fait pour deleted/mise à jour/multi-comptes**
   (tests existants + `test_accepte_le_format_reel_dict_indexe_par_transaction_id`,
   2026-09-11). **Fait le 2026-09-25** pour une réponse vide (`[]` ou `{}`,
   lot vide, le dossier est un succès) et pour un 401 sur un dossier (les
   autres continuent). `/accounts` vide `[]` était déjà couvert (§3.2). Depuis le
   2026-09-22, une ligne malformée est mise en quarantaine sans bloquer le
   lot, et une transaction modifiée ou supprimée après comptabilisation est
   signalée en quarantaine (`workflow/synchro.py`). **Depuis le 2026-09-24**,
   ces deux cas ajoutent aussi l'écriture inverse (journal OD, une seule
   fois) ; l'originale et le nouveau montant ne sont pas réécrits.
8. Ajouter `digifactory_contact_nr` au CSV d'onboarding et à la documentation
   associée (doc 14 §1.2), **en plus de** `bridge_item_id` qui reste réservé au
   futur provider Bridge direct (§8) — pas de renommage, les deux colonnes
   coexistent. **Pas fait** — dépend du point 5.
