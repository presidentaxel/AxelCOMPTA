# 14 — Onboarding et offboarding des tenants

> **État au 2026-11-13** (ajouté ; le reste du doc décrit la cible) :
> - Fait : invitations en masse, renvoi et annulation (AXE-702) ; écran des
>   connexions bancaires Digifactory et relances dans la cloche.
> - Fait : création des dossiers en masse depuis un CSV (« ; » ou « , »,
>   2 000 lignes au plus), rapport ligne par ligne avant toute création
>   (SIREN, combinaison forme × impôt × TVA, dates, doublons, écart avec
>   Sirene), création par le worker (AXE-809, écran « Importer des
>   entreprises »). Le CSV seul, pas de XLSX.
> - Fait : l'import pose le premier exercice, la forme et le code NAF
>   depuis Sirene ; une société cessée n'a pas de dossier, une SAS ou SARL
>   reste « à confirmer » (AXE-834). Le chauffeur confirme sa configuration
>   sur la carte « Vérifiez votre entreprise » ; clôture et liasse
>   l'attendent (AXE-730). Il saisit siège, capital et associés dans « Ma
>   société » (AXE-846). Les écarts avec l'INSEE et le RNE s'affichent dans
>   Entreprises et attendent son choix (AXE-849).
> - Fait : les nouveaux contacts Digifactory sont proposés dans
>   Entreprises (Ajouter, Ignorer), bouton « Synchroniser » (AXE-845) ;
>   tags d'entreprises, dont « chauffeur » d'après le NAF, et exclusion des
>   traitements (AXE-829) ; comptes bancaires retenus ou écartés par le
>   dirigeant (AXE-729, AXE-851).
> - Fait : intégrations du portefeuille en branchements, plusieurs par type
>   (AXE-872). Le chauffeur relie Uber et Bolt via Rollee Connect (AXE-819),
>   relancé tant qu'il ne l'a pas fait (AXE-890) ; un user Rollee existant
>   est relié à son dossier automatiquement ou par le gestionnaire
>   (AXE-911).
> - Fait : reprise d'historique par import du FEC de l'outil précédent
>   (§1.6, AXE-804), par le dirigeant ou l'expert-comptable habilité. Pas
>   fait : la saisie guidée sans FEC, la reprise des immobilisations (à
>   déclarer à la main), les mois d'avant la connexion bancaire (AXE-833).
> - Pas planifié : l'offboarding (§2 export et purge d'un tenant), aucun
>   ticket à ce jour.

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-16

## 1. Onboarding d'un nouveau client (tenant)

### 1.1 Vue d'ensemble

```
Étape 0 — Collecte des données client
Étape 1 — Création du tenant
Étape 2 — Import en masse des dossiers
Étape 3 — Connexion des providers (Bridge + Rollee)
Étape 4 — Reprise d'historique
Étape 5 — Période de vérification sur un dossier pilote
Étape 6 — Bascule complète (go live)
```

Le go live n'est déclenché qu'après la validation de l'étape 5. On ne bascule jamais les 200 dossiers d'un coup sans avoir validé sur 1 ou 2 en premier.

### 1.2 Étape 0 — Données à collecter avant de toucher au code

Données à obtenir du client **avant** de créer quoi que ce soit :

**Pour le tenant :**
- Raison sociale du client gestionnaire, SIREN, contact technique et comptable
- Mode d'usage : portefeuille (N dossiers) ou mono-entreprise
- Pack métier : VTC (pour le pilote), autre secteur à venir
- Providers souhaités : Digifactory (banque, via Bridge — doc 16) ? Rollee ? (les deux pour le pilote)
- Compte Rollee fleet existant ? Contact Digifactory existant (`nr`) ? IDs à récupérer.
- Mode de relance consentements : auto (emails/SMS directs aux chauffeurs) ou manuel (le gestionnaire gère)

**Pour chaque dossier (en masse via CSV) :**

| Colonne | Obligatoire | Exemple | Notes |
|---------|-------------|---------|-------|
| siren | Oui | 821456789 | 9 chiffres |
| raison_sociale | Oui | DUPONT VTC SASU | |
| forme_juridique | Oui | SASU | SASU, SAS, EURL, SARL, EI (matrice `tenants/matrice_statuts.toml`) |
| regime_imposition | Oui | IS | IS, option_IR (239 bis AB, 5 exercices, exige option_ir_debut), IR (EURL, SARL de famille, EI), micro (EI) |
| option_ir_debut | Si IR | 2023 | Année du 1er exercice en option IR |
| regime_tva | Oui | reel_normal | reel_normal, reel_simplifie, franchise |
| tva_recettes_regime | Oui | assujetti_taux_reduit | assujetti_taux_reduit, franchise |
| date_debut_exercice | Oui | 2025-01-01 | ISO 8601 |
| date_fin_exercice | Oui | 2025-12-31 | |
| rollee_driver_account_id | Si Rollee | drv_xxx | Fourni par Rollee ou à créer |
| digifactory_contact_nr | Si Digifactory (V1 pilote) | 12345 | Identifiant pivot bancaire pour le canal actif — doc 16 |
| bridge_item_id | Si Bridge direct | item_xxx | Réservé au futur provider Bridge direct (sandbox, non utilisé en V1 pilote — doc 16 §8) |
| nom_dirigeant | Oui | Jean Dupont | Pour les documents et le profil de pseudonymisation |
| email_dirigeant | Oui | jean@example.com | Pour les liens de signature et relances consentements |
| tel_dirigeant | Optionnel | +33612345678 | Pour SMS de relance consentements |

Ce CSV est validé par le système avant toute création (rapport d'erreurs ligne par ligne). La création en base n'a lieu qu'après validation complète sans erreur bloquante.

### 1.3 Étape 1 — Création du tenant

Via l'interface admin AxeLCompta (non accessible aux clients) :
- Création du tenant avec sa configuration (mode, pack, providers activés)
- Création du/des compte(s) gestionnaire du client — lien `tenant_id`
  (doc 03 §7, doc 19 §2, précisé 2026-09-11 : plus de rôles `admin_tenant`/
  `comptable` distincts, un compte gestionnaire suffit)
- Génération des credentials d'API si le client utilise l'API directement

### 1.4 Étape 2 — Import en masse des dossiers

Upload du CSV validé → le système crée les 200 dossiers en une seule opération :
- Chaque dossier est créé avec sa configuration individuelle (jamais d'héritage implicite)
- Rapport de création : N dossiers créés, M erreurs (avec détail par ligne)
- Les dossiers en erreur ne bloquent pas les autres
- Rollback possible si > 20% d'erreurs (seuil configurable)

### 1.5 Étape 3 — Connexion des providers

**Rollee (mode fleet) :**
- Vérifier que le compte fleet Rollee du client est actif et que les `driver_account_id` existent
- Importer depuis Rollee la liste des comptes fleet pour valider que tous les dossiers ont un compte associé
- Rapport des dossiers sans compte Rollee associé (à connecter manuellement ou par invitation)
- Pour les chauffeurs sans compte : envoyer une invitation Rollee Connect (email avec lien de connexion)

**Digifactory (canal bancaire actif — doc 16) :**
- Vérifier les consentements pour les `digifactory_contact_nr` fournis via l'état `paused`/`data_access`/`last_refresh_status` de `/accounts/{nr}`
- Pour les dossiers sans `nr` : **point ouvert** — pas confirmé si l'ouverture d'une nouvelle connexion Bridge Connect pour un chauffeur passe par Digifactory ou reste hors de notre contrôle (doc 16 §6)
- État des connexions : connexion valide / consentement expiré / en attente

### 1.6 Étape 4 — Reprise d'historique

L'historique de l'outil précédent (EBP, Sage, Cegid, Excel du comptable) est importé au format **FEC** — c'est le format pivot d'import historique, car tous les outils comptables français peuvent l'exporter.

```
Outil précédent → export FEC → validation format DGFiP → import AxeLCompta → golden test de cohérence
```

Vérifications après import :
- Balance équilibrée sur chaque exercice importé
- Soldes 512 cohérents avec les relevés bancaires de référence
- Aucun compte inconnu dans le PCG embarqué (mapping à définir avec le client)
- FEC re-exporté depuis AxeLCompta → identique (à la présentation près) au FEC d'import

Si l'outil précédent ne peut pas exporter de FEC (rare mais possible sur Excel "maison") : import via profil d'import personnalisé (doc 04 §3).

**Reprise Rollee :** une fois les comptes connectés, Rollee peut remonter l'historique disponible (généralement 12-24 mois selon la plateforme). Pour les exercices antérieurs, utiliser les relevés CSV exportés depuis l'espace chauffeur des plateformes.

### 1.7 Étape 5 — Validation sur dossier pilote

Avant go live :
1. Choisir 1 dossier représentatif (SASU IS, actif, bon historique Rollee + Digifactory).
2. Rejouer un mois complet : import Digifactory + Rollee → catégorisation → validation humaine → FEC.
3. Comparer le FEC produit par AxeLCompta avec les écritures de l'outil précédent sur le même mois.
4. Valider avec le service comptable du client que les écritures sont correctes.
5. Seulement si validé → go live sur les autres dossiers.

### 1.8 Étape 6 — Go live progressif

Ne pas basculer 200 dossiers le même jour. Ordre recommandé :
1. Semaine 1 : 5 dossiers (diversité de formes et régimes)
2. Semaine 2 : 20 dossiers
3. Semaine 3-4 : reste du portefeuille

À chaque palier : vérification que les KPIs de catégorisation (doc 01 §6) sont atteints avant de continuer.

---

## 2. Gestion du cycle de vie des consentements (DSP2 + Rollee)

### 2.1 Les deux types de consentement

| Type | Provider | Durée | Conséquence d'expiration |
|------|----------|-------|--------------------------|
| Consentement DSP2 (accès bancaire) | Digifactory (relaie Bridge) | 90 jours — date exposée : `item.authentication_expires_at` (doc 16 §3.2, confirmé 2026-09-11) | Plus de flux bancaire entrant → transactions manquantes |
| Token d'accès plateformes | Rollee | Variable selon plateforme | Plus de données Rollee → settlements non réconciliés |

### 2.2 Dashboard des consentements

Le tableau de bord du gestionnaire affiche en permanence :
- Nombre de consentements valides / expirant dans 14 jours / expirés
- Liste des dossiers concernés avec la date d'expiration
- Statut : actif / à renouveler / expiré / jamais connecté

Ce panneau est un **écran de premier rang**, pas caché dans les paramètres.

**Fait le 2026-09-24, sans écran** : la synchro Digifactory classe et
enregistre le statut du dossier (`consentements_bancaires`) —
`actif` / `a_renouveler` (14 jours ou moins) / `expire` /
`jamais_connecte`. **Fait le 2026-09-25** : la même ligne porte la santé
de connexion (`ok` / `en_pause` / `sans_acces` / `auth_requise` /
`jamais_connecte`) et le rafraîchissement le plus ancien. **Fait le
2026-09-27** : l'écran « Connexions bancaires » du gestionnaire (deuxième
entrée du menu, compteurs, dossiers triés par urgence, statut recalculé à la
lecture), et un encart sur la page Entreprises dès qu'une connexion expire
ou doit être confirmée. Rollee n'est pas couvert.

### 2.3 Modes de relance (configurables par tenant)

**Mode auto :** AxeLCompta envoie directement au chauffeur (email ou SMS selon le canal configuré) :
- J-14 : "Votre connexion expire dans 2 semaines, cliquez ici pour renouveler"
- J-7 : relance
- J-0 : "Connexion expirée, vos données ne sont plus synchronisées"
- Relances automatiques tous les 3 jours après expiration

**Mode manuel :** le gestionnaire reçoit les alertes dans son dashboard et choisit quand/comment contacter ses chauffeurs. Aucune communication n'est envoyée directement au chauffeur par AxeLCompta.

**Configuration par dossier :** un dossier peut être en mode auto pendant que la flotte est en mode manuel (cas : chauffeur qui préfère être contacté directement).

**Fait le 2026-09-27** (`workflow/relances_consentement.py`, migration
`e2b9d7c41f05`) : mode du portefeuille (`auto` par défaut, réglé par un
admin) et exception par dossier (membre ou admin, jamais la lecture seule).
Canal : la cloche de l'espace chauffeur, pas d'e-mail ni de SMS (décision
du 2026-09-26). Paliers : J-14, J-7, à l'expiration puis tous les 3 jours,
une seule notification par palier même si la tâche horaire repasse. Une
connexion que la banque demande de confirmer (SCA à refaire) est relancée
tous les 3 jours, même loin de l'expiration. Pas de rattrapage : un premier
relevé à J-3 envoie le J-7, pas le J-14.

### 2.4 Transactions manquantes pendant un trou de consentement

Si un consentement a expiré pendant N jours, une fois renouvelé :
- Digifactory/Rollee remontent automatiquement l'historique des transactions de la période manquante (dans les limites de leur API — profondeur exacte côté Digifactory non confirmée, doc 16 §6)
- AxeLCompta réimporte et tente la réconciliation rétroactive
- Si des settlements Rollee arrivent sans transaction Digifactory associée (et vice-versa) : file de revue manuelle

---

## 3. Offboarding — départ d'un client

### 3.1 Export complet des données (réversibilité légale)

Le client peut demander à tout moment l'export de toutes ses données. Format de sortie :

| Données | Format | Notes |
|---------|--------|-------|
| Écritures comptables | FEC par dossier par exercice | Standard légal — importable dans tout outil comptable français |
| Balance, grand livre | CSV | Données comptables lisibles |
| Liasses fiscales | PDF (CERFA) | Pour archivage et dépôt |
| Justificatifs | ZIP par dossier | Fichiers originaux sans modification |
| Profils d'import | JSON | Pour reconfigurer un autre outil |
| Journal d'audit | CSV | Qui a fait quoi, quand |

L'export est déclenché depuis l'interface admin AxeLCompta, généré de façon asynchrone (job) et mis à disposition en téléchargement pendant 30 jours.

### 3.2 Délais et procédure

1. Le client notifie la résiliation (email ou interface).
2. AxeLCompta génère l'export complet sous 5 jours ouvrés.
3. Le client dispose de 30 jours pour télécharger.
4. Après confirmation de récupération (ou après 30 jours) : **purge complète** — suppression de toutes les données du tenant en base, des fichiers S3, et des logs nominatifs.
5. Confirmation écrite de la purge (traçabilité RGPD).

### 3.3 Ce que le FEC permet au client

Un client qui part avec ses FEC peut :
- Les importer dans EBP, Sage, Cegid, Pennylane, etc.
- Les fournir à son expert-comptable pour reprendre la main
- Les archiver pour les 10 ans légaux (format légalement reconnu)

C'est la garantie de non-enfermement propriétaire. **Le FEC est le format de sortie pivot — le même que le format d'entrée historique** (doc 02 §4).

### 3.4 Cas particulier : départ en cours d'exercice

Si le client part en cours d'exercice fiscal :
- L'exercice en cours est exporté avec un statut `non_clos` dans le FEC
- Les écritures validées sont complètes ; les propositions non validées sont signalées
- Le client (ou son EC) devra terminer la clôture dans l'outil destination
- AxeLCompta génère un rapport de passation documentant l'état à la date de départ

---

## 4. Onboarding d'un deuxième client (pack métier différent)

Le deuxième client n'est pas dans le secteur VTC. Il a un autre secteur (ex. restauration, BTP). Procédure :

1. **Créer le pack métier** : taxonomie de catégories, règles système, templates d'écritures, config plateformes si besoin. C'est un ensemble de fichiers de données dans `packs/{secteur}/`, pas du code.
2. **Configurer le tenant** avec `pack: {secteur}`.
3. **Suivre les étapes 1-6** du §1 ci-dessus — elles sont identiques quel que soit le secteur.

La durée de création d'un nouveau pack est proportionnelle à la complexité métier, pas à la complexité technique. Le moteur ne change pas.

Si le nouveau client utilise Digifactory/Bridge mais pas Rollee (secteur sans plateforme gig) : configurer `platforms: none`. La réconciliation de settlements ne s'active pas, et aucun code n'est exécuté inutilement.
