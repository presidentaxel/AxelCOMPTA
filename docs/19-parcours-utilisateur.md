# 19 — Parcours utilisateur : gestionnaire et chauffeur

> Statut : brouillon à valider — Dernière mise à jour : 2026-11-10 (exception expert-comptable en place, §2.4).
> Né d'une discussion Louis / Claude Code le 2026-09-06 : décision de
> cadrer et documenter l'accès chauffeur en libre-service **avant** tout
> code, conformément à ce que prévoyait déjà [doc 12 §2.7](12-roadmap-todo.md).
> Ce doc complète [doc 11](11-ux-ui.md) et [doc 14](14-onboarding-offboarding.md)
> — il ne les remplace pas, mais **corrige une hypothèse fausse qu'ils
> partageaient tous les deux jusqu'ici** (§2.1 ci-dessous).
>
> **Révision structurante du 2026-09-11 (Louis)** : nos deux catégories de
> client ne sont pas au même niveau. Le **client interface** — celui qui
> utilise vraiment le produit, dossier par dossier — c'est **l'indiv**
> (le chauffeur/dirigeant). Le **client de gestion globale** — celui avec
> qui on signe un contrat — c'est la **plateforme** (le gestionnaire
> portefeuille). Conséquence directe, qui corrige §2.1 telle qu'écrite au
> 2026-09-06 : la file de revue, l'instruction d'alerte, la clôture et la
> signature **ne sont plus des écrans gestionnaire** — ce sont des écrans
> indiv, parce que c'est l'indiv qui a dépensé, qui sait, et dont c'est la
> donnée. Le gestionnaire garde un état des lieux agrégé et l'onboarding,
> rien de plus (§6 refaite). Recoupe doc 02 §2.3 (« l'utilisateur
> professionnel valide ») : c'est l'indiv, cet utilisateur professionnel,
> pas le gestionnaire.

## 1. Pourquoi ce doc

Jusqu'ici, le chauffeur n'existait dans la doc qu'à travers **un seul
écran** : la page de signature (doc 11 §3.3), zéro compte, lien + OTP. Ce
n'est plus le cas. Le chauffeur doit maintenant avoir **son propre compte**,
relié à ses propres écritures bancaires, avec une vraie application — pas
un lien ponctuel. Ce doc décrit ce parcours, celui du gestionnaire tel qu'il
évolue en conséquence, et sert directement de base au nouveau [doc 17](17-plan-demo-backend.md)
(plan de démo).

## 2. Un compte, deux liens — pas deux systèmes

> **Précisé le 2026-09-11 (doc 03 §7)** : « gestionnaire » et « indiv » ne
> sont pas deux types de compte différents, deux systèmes d'auth à
> construire séparément. **Un compte peut porter un lien `dossier_id`**
> (accès indiv à ce dossier, §2.2) **et/ou un lien `tenant_id`** (accès
> gestionnaire à ce portefeuille, §2.1) — les deux indépendamment, les
> deux à la fois possible sur le même compte (§2.3, le mono). Ce qui suit
> décrit ce que chaque lien donne comme accès, pas deux produits
> distincts.

### 2.1 Le gestionnaire (PC / web) — **corrigé le 2026-09-11** : état des lieux, pas cockpit détaillé

**Ce que ce doc disait avant (2026-09-06) était faux sur un point
important** : « rien ne change sur l'interface portefeuille, file de
revue et clôture incluses ». En fait si — la file de revue (doc 11 §3.1),
l'instruction d'alerte (doc 11 §3.2), la clôture (doc 06 §5) et la
signature (doc 11 §3.3, doc 20) **deviennent des écrans indiv**, pas
gestionnaire (§2.4 explique pourquoi). Ce qui reste vraiment côté
gestionnaire :

- Dashboard portefeuille : **agrégats seulement** (CA/charges/résultat par
  dossier, nombre de dossiers actifs, régime TVA/statut) — pas le détail
  d'une transaction, jamais.
- **Visibilité de premier rang sur l'onboarding** de ses indivs : qui a un
  compte actif, qui a été invité et n'a pas répondu, qui n'a toujours pas
  de compte (§3.2, inchangé).
- Invitation, individuelle ou en masse (§3.1, étendu le 2026-09-11).
- **Écran au 2026-09-25, soir** : le mot affiché est **entreprise**, pas
  chauffeur. La liste est sur `/portefeuille`. À côté du nom : Compte
  ouvert, Invitation envoyée ou Compte fermé, et le résultat. Deux frises
  par ligne, l'année en cours et l'année d'avant. La frise est un palier
  grossier, pas le détail que §2.4 réserve encore à une confirmation
  juridique.
  - **Compte** regroupe l'invitation, le profil et la banque. Une fois
    le compte ouvert, l'étape est faite pour toutes les années.
  - Le reste est réglementaire, par exercice (doc 02 §4 et §6, §5.3,
    doc 20 §4bis) : Clôture, Signature de validation, dépôt au Greffe,
    dépôt aux Impôts, Signature légale. L'année d'avant est celle qu'on
    traite pendant le début de l'année en cours : sa frise porte sa vraie
    étape, jamais tout cochée d'office. Le dossier n'a qu'un exercice : s'il
    est terminé, c'est l'année d'avant ; sinon c'est l'année en cours, et
    l'année d'avant est « Sans exercice » faute de données.
  - Pas de nombre d'écritures, pas de justificatif, pas de pièce. Après
    le compte, chaque étape de l'année d'avant est une preuve
    (`documents_signes`), dans l'ordre : clôture, signature de
    validation, greffe, dépôt aux impôts, signature légale. La frise
    s'arrête au premier jalon absent. Ajouter ou retirer une preuve
    déplace l'étape. L'année en cours ne montre que le compte.
  - Le nom de l'organisation (`tenants.nom`) se change dans le menu du compte
    (l'avatar, en bas de la barre latérale), qui défile avec la
    page. Invitations est le lien en haut à droite de la liste, et n'est
    plus dans la barre.
  - **Rappels** (`/rappels`) : règles SMS, e-mail ou appel, pour toutes
    les entreprises ou certaines, manuelles ou N jours avant la clôture.
    L'envoi n'est pas branché. Trois règles de base sont posées au
    premier passage. Les boutons correspondants sont sur la fiche.
  - **Équipe** (`/equipe`) : Admin (nom, équipe, retraits, règles),
    Membre (invitations et rappels), Lecture. Un compte déjà là sans
    ligne de droit est admin.
  - **Intégrations** (`/integrations`) : un faux Digifactory, branché par
    défaut. Branché, l'app chauffeur ne propose pas « Connecter ma banque ».
    Le débrancher depuis cet écran réaffiche l'option. Bridge, Volubile, SMS
    et e-mail restent annoncés comme prévus.
  - Retirer une entreprise la masque de la liste (`dossiers.retire_le`).
    Les écritures restent.

### 2.2 Le chauffeur (mobile) — nouveau

Le chauffeur a son propre compte, sa propre app (webapp responsive pour la
démo, cible finale = app native App Store / Play Store). Ce compte lui sert
à :

- Voir ses propres transactions bancaires et leur catégorisation.
- Prendre en photo ses tickets/justificatifs au fil de l'eau.
- Répondre à de petites questions de catégorisation quand le système hésite.
- Optionnellement connecter lui-même sa banque (§4).
- Signer ses documents (l'écran qui existait déjà, doc 11 §3.3 — il devient
  une étape parmi d'autres, pas le seul écran).

### 2.3 Mode mono-compte — **résolu le 2026-09-11**, ce n'est même plus un « mode »

**La tension notée dans une version précédente de ce doc est résolue.**
Un indépendant qui gère sa propre compta seul n'a pas de statut spécial :
c'est un compte dont le lien `tenant_id` (gestionnaire) et le lien
`dossier_id` (indiv) **pointent vers le même portefeuille d'un seul
dossier — le sien** (doc 03 §7). Aucun branchement particulier à coder :
- Il a accès à l'écran gestionnaire (§2.1) — état des lieux agrégé —
  **qui n'affiche qu'un seul dossier**, le sien. Techniquement inutile
  (pas grand-chose à agréger sur un portefeuille de un), mais pas un
  écran en moins ni un cas à exclure.
- Il a accès à l'écran indiv (§2.2) — son propre dossier en détail,
  transactions, revue, clôture, signature.

Les **deux** interfaces (web et mobile/webapp) restent celles déjà
décrites §7 — rien de spécifique au mono à construire là non plus,
c'est la même personne qui navigue entre les deux, pas un habillage à
part.

### 2.4 Ce que le gestionnaire ne voit jamais (et ce qui reste à confirmer légalement)

Le gestionnaire n'a **aucun accès** aux transactions, justificatifs,
détail des écritures ou documents d'un dossier — c'est la donnée de
l'indiv, générée par ses propres dépenses, pas celle du gestionnaire.
Même le fait de savoir si une pièce a été signée ou déposée est **une
donnée dérivée de la comptabilité d'un tiers**, pas un simple statut
technique anodin — Louis n'est pas certain que même *ça* soit conforme
RGPD/monopole d'expertise comptable (doc 02 §2, doc 02 §10). Tant que ce
n'est pas confirmé par un juriste : **le gestionnaire ne voit rien de
dossier-spécifique au-delà des agrégats de §2.1** — pas d'option cachée
activée par défaut en attendant.

**Exception, décidée le 2026-11-05 : l'expert-comptable de l'entreprise.**
Une entreprise qui gère sa flotte avec un expert-comptable peut lui donner
le rôle `expert_comptable`. Lui seul voit le détail des dossiers couverts
par sa lettre de mission et peut y imputer, après avoir accepté un
engagement de responsabilité ; chaque changement porte son nom et son
motif, et le chauffeur les voit (doc 02 §2.3, AXE-800). Le logiciel ne
décide pas à sa place. Un gestionnaire sans ce rôle garde la vue agrégée. En
place depuis le 2026-11-09 : le mode expert, les anomalies, les opérations
classées et la quarantaine ne s'ouvrent qu'à l'expert habilité, sur les
dossiers de sa lettre de mission.

## 3. Modèle de compte et onboarding

### 3.1 Qui crée quoi

**Pas de self-signup public.** Le tenant (le gestionnaire) est toujours créé
par AxeL — ça ne change pas par rapport à doc 14 §1.3. Ce qui est nouveau :
chaque chauffeur doit ensuite avoir **son propre compte utilisable**, pas
juste une ligne en base créée par CSV (doc 14 §1.2/1.4). Deux façons d'y
arriver, non exclusives :

- **Le gestionnaire invite lui-même ses chauffeurs** depuis son interface
  (self-service à ce niveau-là, pas au niveau tenant) — soit **au lien
  individuel** (un email à la fois, déjà construit), soit **en masse
  depuis une base clients** (nouveau, précisé 2026-09-11 : import d'une
  liste — CSV a minima — qui déclenche une invitation par ligne, avec
  rapport d'envoi succès/erreur par ligne, même logique que l'import de
  dossiers doc 14 §1.4 mais pour des invitations, pas des configurations
  comptables). **Distinct** du CSV dossiers (doc 14 §1.4) : celui-ci crée
  des comptes utilisables, l'autre configure des dossiers — un gestionnaire
  peut avoir besoin des deux, dans n'importe quel ordre.
- **AxeL peut assister** le gestionnaire pour cette étape s'il en a besoin
  (mêmes principes que l'aide à l'onboarding déjà prévue doc 14).

Le CSV en masse (doc 14 §1.4) continue d'exister pour créer les *dossiers*
(configuration comptable) ; l'invitation chauffeur est une étape
supplémentaire et distincte qui donne accès à *un compte utilisable*, pas
seulement à une fiche.

### 3.2 Visibilité gestionnaire sur l'onboarding des chauffeurs

Extension directe du pattern déjà existant pour les consentements bancaires
(doc 14 §2.2, « écran de premier rang, pas caché dans les paramètres ») —
plutôt que d'inventer un nouveau concept, le même panneau affiche aussi le
statut d'invitation par chauffeur :

| Statut | Sens |
|---|---|
| `non_invité` | Dossier créé, aucune invitation envoyée |
| `invité` | Invitation envoyée, en attente de réponse |
| `compte_créé` | Le chauffeur a créé son compte mais pas terminé son propre onboarding (§5) |
| `actif` | Compte utilisé normalement |
| `inactif` | Compte créé mais plus utilisé depuis N jours (seuil à définir) |

### 3.3 Option avancée : synchronisation API — prévue, pas construite pour la démo

Certains gestionnaires ont leur propre base de données de chauffeurs.
Fonctionnalité prévue : une connexion API vers cette base, avec détection
des nouveaux chauffeurs et, **en option explicite (opt-in, désactivée par
défaut)**, envoi automatique d'une invitation dès qu'un nouveau chauffeur
apparaît côté gestionnaire. Ce n'est **jamais** un comportement par défaut —
le gestionnaire doit l'activer consciemment dans ses réglages.

Cadré ici pour ne pas avoir à le repenser plus tard, mais **hors scope de
la démo** (doc 17) — c'est un vrai chantier d'intégration (auth API tierce,
mapping de champs, sécurité) qui n'apporte rien à la validation du parcours
et des calculs.

## 4. Connexion bancaire : deux modes, par dossier

Le principe déjà acté « statut/régime = configuration de premier rang par
dossier » (doc 06 §7, doc 03 §3bis) s'étend à l'accès bancaire. Un nouveau
champ de configuration, au même niveau que `regime_imposition` ou
`tva_recettes_regime` (doc 14 §1.2) :

| `mode_acces_bancaire` | Qui connecte | Cas d'usage |
|---|---|---|
| `gestionnaire` | Le gestionnaire, via Digifactory (doc 16) | Cas pilote actuel — l'indiv n'a rien à connecter : soit les transactions arrivent directement dans son app (déjà remontées côté Digifactory), soit un écran « ça arrive bientôt » tant qu'elles n'y sont pas encore — jamais de bouton Bridge affiché dans ce mode. Un `contact_nr` posé (Digifactory branché) a le même effet, même si le mode du dossier était encore `chauffeur_direct` : pas de seconde connexion. En démo, le faux Digifactory d'Intégrations est branché par défaut et masque l'option pour tous les dossiers ; le débrancher la réaffiche. |
| `chauffeur_direct` | L'indiv lui-même, depuis son app, **via Bridge en direct** (précisé 2026-09-11, doc 16 §8) | Indiv autonome sans agrégateur côté gestionnaire — le bouton de connexion bancaire dans l'app **est** Bridge Connect, pas un choix parmi d'autres. |

Les deux passent par la même interface `DataProvider` (doc 13 §2) — aucun
changement dans le moteur selon le mode retenu, seule la configuration du
dossier change. **`chauffeur_direct` reste bloqué techniquement** tant que
`BridgeProvider` (doc 16 §8, doc 12 §1.2) n'est pas construit — c'est un
vrai prérequis, pas du réagencement d'écran ; le bouton actuel (doc 17 §9)
est un stub visuel volontaire en attendant. Le dashboard de consentements
(doc 14 §2.2) s'étend pour couvrir les deux : quand c'est l'indiv qui
connecte lui-même, c'est lui qui reçoit les relances d'expiration de
consentement (et non le gestionnaire) — cohérent avec le mode de relance
déjà configurable par dossier.

**Pour la démo (doc 17)** : les deux modes sont visibles à l'écran (le
réglage existe, l'UI existe). Le mode `gestionnaire` (Digifactory) est
câblé en priorité — c'est le cas réel du pilote. Le mode `chauffeur_direct`
est un objectif « si le temps le permet » (§6), pas un bloquant — Louis
relance Digifactory sur le token (doc 16 §7) pour que ce chemin fonctionne
réellement avant la fin du mois.

## 5. Parcours détaillé — l'indiv (mobile/webapp) — **réécrit le 2026-09-11**

**Ce parcours porte maintenant tout ce qui touche à ses propres données** :
transactions, revue, justificatifs, clôture, signature. Rien de tout ça
n'existe plus côté gestionnaire (§2.1, §2.4).

### 5.1 Onboarding

1. **Réception de l'invitation** (email/SMS) envoyée par le gestionnaire ou AxeL.
2. **Création de compte** — email + mot de passe (ou lien magique), pas de
   self-signup libre, mais un vrai compte personnel. **Option de changer
   son mot de passe** (précisé 2026-09-11) — pour la confidentialité, le
   mot de passe initial (lien d'invitation) ne doit pas rester le seul.
   **Fait le 2026-09-25** (démo, REST Supabase, sans SDK) : les écrans
   `/connexion` et `/chauffeur/login` proposent le mot de passe, le lien
   magique (`create_user: false`) et le mot de passe oublié. Les trois
   liens (magique, réinitialisation, confirmation d'une nouvelle adresse)
   arrivent sur `/auth/lien`. Le changement d'adresse et de mot de passe
   d'une session déjà ouverte est sur `/compte` (gestionnaire) et
   `/chauffeur/compte`. Dans le dashboard Supabase (Authentication → URL
   Configuration), ajouter `http://localhost:3000/auth/lien` et l'URL
   d'invitation chauffeur aux Redirect URLs ; si le lien retombe quand
   même sur la racine du site, le fragment `#access_token` est repris
   vers `/auth/lien`. Une invitation chauffeur (`dossier_id`) va sur
   `/chauffeur/accepter-invitation` ; une invitation d'équipe (`tenant_id`)
   reste sur `/auth/lien`. Les deux demandent le mot de passe.
3. **Complément de profil** si nécessaire (une partie est déjà pré-remplie
   depuis la fiche dossier créée côté gestionnaire).
4. **Connexion bancaire** — trois cas concrets selon `mode_acces_bancaire`
   (§4, précisé 2026-09-11) :
   - `chauffeur_direct` : il relie sa banque **via Bridge**, dans l'app.
   - `gestionnaire`, transactions déjà remontées : il les voit directement,
     rien à connecter.
   - `gestionnaire`, rien encore remonté : écran d'attente explicite
     (« vos transactions arrivent bientôt »), pas un vide silencieux.

### 5.2 Traitement au fil de l'eau — pas une revue de fin d'année

**Principe central, précisé 2026-09-11** : dès qu'une transaction arrive et
que le pipeline (règles/ML/LLM) ne sait pas trancher, l'indiv reçoit une
**notification** pour la traiter au plus vite — pas une pile qui s'accumule
jusqu'à la clôture. Bénéfice double : plus simple pour l'indiv (petit flux
continu, pas une session marathon en fin d'exercice), et ça répartit la
charge de notre côté (support, LLM, instruction) sur l'année plutôt que de
tout concentrer sur la période de clôture — risque déjà identifié doc 09
§7 (charge, clôtures groupées).

5. **Vue de ses transactions** : ce qui a été catégorisé, ce qui reste à
   trancher — version simplifiée, langage clair, pas le vocabulaire
   comptable pro.    **Écran au 2026-09-25** : l'app s'ouvre sur l'arriéré (« À traiter »),
   qui se termine. « Mouvements » est un relevé d'un mois, jour par jour,
   ouvert sur les sorties : les entrées sont un second filtre, on leur
   demande moins de justificatifs. Pas la liste de toutes les écritures.
   L'exercice porte le résultat, puis « Pour les impôts » : la liasse et
   les pièces à conserver (2065, FEC, grand livre, balance). Le
   téléchargement de la liasse demande de cocher que les comptes ne sont
   pas clôturés et qu'AxeLCompta n'en est pas responsable. Si la clôture
   est faite, la même fenêtre demande aussi d'avoir lu et validé la liasse
   (la signature électronique n'est pas encore dans l'application). Rien
   de tout ça ne s'ouvre au chargement. La télédéclaration n'est pas faite
   ici. « Greffe » donne ensuite les réponses à reporter sur le portail
   INPI et les pièces au nom du guichet, selon la forme et la taille.
   C'est
   un second écran. Barre du bas : Activité,
   Exercice, Compte. Colonne étroite, faite pour le téléphone et centrée
   sur un grand écran.
6. **Notification + petite question de catégorisation** quand le système
   hésite (« repas ou autre ? », « personnelle ou pro ? ») — dès que la
   transaction arrive, pas en lot différé. Même logique que l'ancienne
   « file de revue » (doc 11 §3.1) — **cet écran est maintenant ici, plus
   côté gestionnaire** (§2.1).
7. **Photo de justificatif** au fil de l'eau. **Écran au 2026-09-25** : pas
   un bouton sur chaque ligne, même s'il n'y a encore aucune photo. Une
   carte pour les dépenses du dernier mois : « Photographier un ticket ».
   La lecture est simulée (l'OCR viendra plus tard, le fichier décide de
   façon stable) : si enseigne et montant collent, on confirme ; sinon
   l'écran dit pourquoi (montant ou enseigne) et propose un autre mouvement.

**Système de notification : interne depuis le 2026-09-26** (cloche de
l'espace chauffeur, regroupé par dossier, anti-harcèlement, sans donnée
comptable ; posé toutes les heures par `axelcompta.taches`). Pas d'e-mail
envoyé par AxeLCompta (Louis, 2026-09-26) : e-mail et SMS sont des
intégrations que le gestionnaire branche lui-même, non construites. Écrit
avant, à l'origine : « entièrement à construire, rien n'existe » — un vrai
chantier technique, pas une case UI à ajouter.

### 5.3 Clôture — la boucle de complétude bancaire

8. **Demande de clôture** en fin d'exercice : l'indiv confirme que la
   dernière écriture connue correspond bien à sa vraie banque (doc 06 §5bis
   — c'est cette confirmation, pas une date, qui fait foi). Tant que ce
   n'est pas confirmé, chaque nouvelle synchro Bridge/Digifactory qui
   remonte de nouvelles écritures redemande cette confirmation.
9. Une fois confirmé (et comme le traitement s'est fait au fil de l'eau,
   §5.2 — pas de gros arriéré à traiter d'un coup) : génération des
   documents (greffe, INPI, TVA, liasse — doc 06 §6, doc 20).
10. **Première signature — la validation** (notification dédiée) : l'indiv
    atteste être d'accord avec les comptes tels que produits. **Cette
    signature nous protège** (doc 02 §2.3 : « l'utilisateur professionnel
    valide ») — elle n'a pas besoin d'être qualifiée RGS, ce n'est pas la
    même chose que la signature légale de dépôt (doc 20 §4bis).
11. **Envoi** vers les organismes concernés (impôts, greffe, INPI, TVA…).
12. **Seconde signature — la légale** : certains organismes renvoient des
    documents à signer après coup (ex. le document de synthèse INPI,
    doc 20 §4) — c'est là qu'intervient la vraie signature qualifiée RGS,
    par indiv, jamais par AxeLCompta (doc 20 §6, tranché 2026-09-11).

## 6. Parcours détaillé — le gestionnaire (PC / web) — **réécrit le 2026-09-11**

**Beaucoup plus court qu'avant** : plus de file de revue, plus de clôture,
plus de signature — tout ça a migré côté indiv (§5). Ce qui reste :

1. Réception du tenant configuré par AxeL (doc 14 §1.3) — AxeL signe avec
   le gestionnaire (contrat B2B), pas avec chaque dossier individuellement.
2. Import en masse des dossiers (CSV, doc 14 §1.4) — configuration
   comptable de chaque indiv.
3. **Invitation des entreprises** — une entreprise et un e-mail, depuis
   `/invitations` (lien en haut à droite de la liste, §3.1). Le collage
   en masse reste disponible dans l'API, plus comme bloc de texte sur
   l'écran. Le suivi d'onboarding (§3.2) est le mot à côté du nom.
4. **Liste, état des lieux** (§2.1) : résultat, compte ouvert ou fermé,
   frise réglementaire de l'année en cours et de l'année d'avant. Jamais
   le détail d'une transaction ou d'un justificatif. La fiche pousse la
   liste ; elle porte les rappels préparés et le retrait, avec
   confirmation.
5. **Rappels, équipe, intégrations, compte** — réglages décrits au §2.1.
   Le compte (`/compte`) porte le nom de l'organisation, l'e-mail et le
   mot de passe.

## 7. Portée technique

- **Démo** : webapp responsive pour le rôle chauffeur (ouverte depuis un
  téléphone, pas d'installation), webapp desktop classique pour le rôle
  gestionnaire — même socle front, deux habillages, cohérent avec le
  principe déjà acté doc 11 §1bis (mono = portefeuille sans la couche
  portefeuille — même logique appliquée ici entre gestionnaire et
  chauffeur : composants partagés, habillage différent).
- **Cible finale** (post-démo) : app native chauffeur sur App Store / Play
  Store. Le gestionnaire reste PC/web — aucune ambition mobile de ce côté.

## 8. Ce qui reste ouvert (non traité ici)

- Design précis des écrans mobiles (DESIGN.md n'a aujourd'hui de règles
  mobiles que pour la page de signature, doc DESIGN.md « Comportement
  responsive ») — à faire une fois ce parcours validé, avant le code.
- Détail technique de l'option de synchronisation API (§3.3) — volontairement
  laissé pour plus tard.
- Seuil d'inactivité pour le statut `inactif` (§3.2) — à définir avec Louis
  à l'usage, pas bloquant pour la démo.

**Ajoutés le 2026-09-11, chantiers réels pas encore scopés** :

- **Système de notification** (§5.2) — **interne depuis le 2026-09-26**
  (e-mail du 2026-09-22 retiré) : une notification regroupée par dossier
  dans la cloche, reposée seulement s'il y a des opérations nouvelles (pas
  avant 6 h) ou en rappel hebdomadaire, sans montant ni libellé. E-mail et
  SMS : intégrations côté gestionnaire, à construire.
- **Import en masse des invitations** (§3.1, §6) — **fait le 2026-09-22** :
  collage ou fichier `dossier_id, e-mail`, 500 lignes au plus, résultat par
  ligne ; distinct du CSV dossiers déjà spécifié doc 14 §1.4 (à faire pour
  le pilote).
- **Boucle de clôture/complétude bancaire** (§5.3, doc 06 §5bis) — durée du
  délai de battement et politique CCA/FNP précise à valider avec un
  expert-comptable ; mécanique de redemande de confirmation à chaque
  nouvelle écriture pas encore détaillée techniquement.
- **`BridgeProvider` direct** (§4, doc 16 §8, doc 12 §1.2) — prérequis
  technique du mode `chauffeur_direct`, pas commencé.
- **Confirmation juridique sur la visibilité gestionnaire** (§2.4, doc 02
  §10) — bloquant pour savoir si même « documents déposés : oui/non » est
  affichable au gestionnaire.
- ~~Rework de ce qui a été construit le 2026-09-11 avant cette révision~~
  — **fait le 2026-09-11, même jour** : `ClotureSection.tsx` et
  `GreffeInpiSection.tsx` ont migré vers `/chauffeur/[dossierId]`, appel
  de signature authentifié (`signerGreffeInpiChauffeur`,
  `lib/auth-chauffeur.ts`) pour que `api/routes.py` attribue vraiment la
  signature à l'indiv connecté. La fiche dossier gestionnaire
  (`app/(gestionnaire)/dossiers/[id]`) et `TrancherActions.tsx` sont
  supprimés — le gestionnaire n'a plus que le dashboard agrégé (§2.1),
  les cartes n'ouvrent plus rien (`Link` retiré). Vérifié en vrai
  navigateur (compte de test Sophie via `/admin/users`, supprimé après) :
  connexion, clôture et greffe/INPI visibles et fonctionnels côté indiv,
  signature réelle en direct (badge → signé, PDF change), dashboard
  gestionnaire avec cartes non cliquables. `next lint`/`build` verts.
  **Pas fait dans ce lot** (hors scope, cf. §7bis) : durcir l'accès
  anonyme encore permis par le backend sur ces routes (et sur
  transactions/décision/justificatif, préexistant) — resterait
  accessible sans jeton si quelqu'un appelait l'API directement.

### 8bis. Jeton obligatoire + preuve de signature — **fait le 2026-09-11, même jour**

~~Les routes indiv de `api/routes.py` acceptaient un appel sans en-tête
`Authorization`~~ — corrigé. Louis (même jour, suite immédiate) : « on
peut faire les appels avec les jetons pour la sécu... et avec des logs, je
veux pouvoir prouver légalement que la personne a signé donc il faut une
trace électronique. »

**Doc déjà écrite pour ça, pas inventée ici** : doc 10 spécifie déjà
« Journal d'audit : table append-only — qui a vu/modifié/validé/exporté
quoi, quand, depuis où » (V1, doc 12 §1.1). Une première tranche existe
depuis le 2026-09-24 (`journal_audit`, migration `c2f91ab84e30`) : qui a
posé une décision ou une signature, quand, sur quel dossier. Pas de
libellé bancaire, pas de PDF. Le journal « qui a consulté / exporté »,
consultable dans l'UI, reste à faire. Ce lot du 2026-09-11 en avait fait
la version minimale, appliquée aux deux points qui en avaient le plus
besoin :

1. **Jeton obligatoire sur toutes les routes indiv** (`_verifier_acces_dossier`
   renvoie désormais `IdentiteAuthentifiee`, pas `None` — 401 si aucun jeton,
   403 si mauvais dossier). Le stub `UTILISATEUR_DEMO` est retiré : plus
   aucune route de tranchage/signature n'a de chemin gestionnaire-sans-login,
   cohérent avec §2.1/§2.4 (ces actions sont indiv-exclusives). `GET
   /dossiers/{id}` (détail, pas la liste) est concerné aussi — plus rien
   dans l'app ne l'appelait anonymement depuis le déplacement de §8.
2. **`SignatureRepository` devient append-only** (`workflow/signature.py`,
   doc 20 §4bis) — écart trouvé dans le lot précédent : une signature
   pouvait être écrasée par la suivante (« pas besoin d'historique pour la
   démo », raisonnement erroné une fois qu'il faut prouver légalement
   qu'une personne a signé). `dernier()` reste l'API principale, `lister()`
   expose l'historique complet, jamais purgé. Depuis le 2026-09-24,
   `UPDATE` et `DELETE` sont aussi refusés en base sur `documents_signes`
   (migration `d8b41c6e0a27`, même trigger que les écritures), et chaque
   signature écrit une ligne dans `journal_audit`.

**Reste à faire, plus large** (doc 10, doc 12 §1.1) : le journal
transverse (consultations, exports, pas seulement décisions et signatures)
et son écran. La tranche décisions/signatures est en place (2026-09-24).

Vérifié : 231 tests backend verts (dont 45 dans `test_demo_api.py`, un
test devenu obsolète supprimé — `test_decision_gestionnaire_reste_attribuee_a_utilisateur_demo`,
plus aucun chemin gestionnaire-sans-jeton n'existe pour le déclencher),
mypy/ruff/import-linter verts.
