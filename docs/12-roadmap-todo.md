# 12 — Roadmap et TODO maître

> Statut : brouillon à valider. Dernière mise à jour : 2026-11-13.
> **Seule source de l'état du projet dans le repo** (fait, en cours, prévu).
> Le suivi au jour le jour est dans Linear, projet
> [Axel Compta — V1 prod](https://linear.app/axel-project/project/axel-compta-v1-prod-api-ingestion-fiabilite-899778ce7b41)
> (P-AXE-28) ; ce doc en donne la photo et les décisions. Les docs 17 et 18
> n'en tiennent pas de copie.
>
> Capacité : Louis sur le produit, Arthur en renfort depuis fin octobre
> (revues UX AXE-563/564, performance AXE-565 à 567). Une partie du code
> d'octobre et de novembre est écrite par des agents (Cursor) et relue par
> Louis.
>
> Le recalage de septembre (jalons J1 à J6, travail du 21/09 au 27/09, PR
> #3 à #39) est archivé tel quel dans
> [archive/12-recalage-2026-09.md](archive/12-recalage-2026-09.md).

## État au 2026-11-13 (à lire avant tout le reste)

**En une phrase :** du 10 au 13/11, 41 PR (#125 à #165) ont livré le cœur
comptable VTC qui manquait : recettes Uber et Bolt lues chez Rollee et
ventilées en 706, TVA et commission ; TVA déductible des dépenses ;
véhicule amorti ou en LOA ; bilan d'ouverture repris d'un FEC ; identité de
la société et registres officiels. L'IA (Claude Fable 5.2) propose une
catégorie dans la synchro, sous budget, éteinte par défaut. L'interface est
passée au design system v2. Ce qui manque pour la V1 : **un mois réel
exporté** (AXE-733), et la mise en production.

**Où on en est par rapport au plan.** Projet « V1 prod » (cible
**31/12/2026**, initiative « Prod-ready trio → Market janv. 2027 ») :
l'analyse critique du 05/11 est presque soldée côté code (AXE-802, 803,
804 faits ; AXE-801 reste, en secours de Rollee). **Pas encore fait** : la
première synchro des chauffeurs réels (AXE-728) et le mois exporté
(AXE-733). Aucun dossier `DIGI_` n'a encore été tranché ni clôturé de bout
en bout.

**Attention : code mergé ≠ production à jour.** Rien de la semaine ne
tourne sur la base réelle tant qu'AXE-842 n'est pas fait : 14 migrations
depuis le 10/11, les clés à poser (Rollee, INSEE/RNE, S3, Anthropic), les
reprises en simulation puis appliquées (TVA déductible, décisions,
comptes bancaires), la crontab. Mode d'emploi :
[backend/README.md](../backend/README.md), « Mettre en route les tickets
du 10 au 13/11 ». Des écritures restent au 471 depuis la synchro sans
modèle du 05/11 (AXE-850).

**Rien de ce qui suit n'a encore tourné sur de vraies données** : les
réponses de Rollee, de l'INSEE et du RNE sont construites d'après leur
documentation, l'IA n'a pas été appelée depuis la synchro, aucun vrai FEC
n'a été repris. Chaque PR dit comment le vérifier.

Client de référence V1 : Serenity Gestion, installé étape par étape avant
toute autre vente.

### Fait du 2026-11-10 au 2026-11-13 (PR #125 à #165)

**Recettes des plateformes : Rollee de bout en bout (AXE-817 à 821, 872,
889 à 891, 911)**
- Plusieurs intégrations de chaque type par portefeuille (AXE-872, #132) :
  un **branchement** nommé par accès (mail, SMS, Digifactory, Rollee), un
  par défaut (sauf Rollee : tous les comptes sont interrogés tant qu'un
  dossier n'est pas relié à l'un d'eux), et un choix possible par dossier. La synchro Digifactory
  ouvre un client par jeton ; `DIGIFACTORY_TOKEN` ne sert plus qu'en repli.
  `integrations_envoi` est repris puis supprimé.
- Client Rollee (AXE-818, #133) : jeton JWT par branchement (sandbox ou
  production), renouvelé sur 401 et **toujours gardé** ; 429 et 5xx
  réessayés. Une période qui ne tombe pas juste (brut − frais ≠ versé,
  devise, troisième décimale) est mise de côté, jamais arrondie. Unité des
  montants non documentée par Rollee : euros supposés, à vérifier au test
  de contrat (`pytest -m rollee`).
- Le chauffeur relie Uber et Bolt dans Rollee Connect, depuis Compte › Mes
  plateformes (AXE-819, #134). Le gestionnaire voit « Plateformes reliées :
  1/2 », sans montant.
- Webhooks signés `POST /webhooks/rollee/{branchement}` et rattrapage
  quotidien à 4 h (AXE-820, #135). Le gestionnaire prépare le webhook de
  chaque compte dans Intégrations (adresse, secret, cases à cocher chez
  Rollee), une fois l'API en ligne (AXE-811).
- Revenus → rapprochement → **OD de ventilation** 706 HT, 44571, 622, 44566
  (autoliquidation Bolt), sans toucher au virement ni au 512 (AXE-821,
  #136). Golden test doc 13 §5.3 au centime ; rejouer n'écrit rien. États :
  rapproché, en attente de banque, à classer, à vérifier, quarantaine.
- Un virement reclassé hors recette perd sa ventilation, dans la même
  transaction que la décision (AXE-889, #157).
- Rappel automatique « reliez vos plateformes » (AXE-890, #158).
- Les versements « à vérifier » entrent dans « À traiter » avec leur motif
  en clair ; le gestionnaire n'en voit que le nombre (AXE-891, #163). Un
  versement « à vérifier » ne peut pas encore en sortir : AXE-912.
- Rapprochement automatique user Rollee ↔ dossier (AXE-911, #165), par
  empreintes HMAC (metadata, IBAN, nom avec e-mail ou téléphone). Le doute
  va au gestionnaire (Entreprises, « N comptes Rollee attendent votre
  choix »). Retirer un lien contre-passe les ventilations. **Éteint** tant
  que `AXELCOMPTA_ROLLEE_RAPPROCHEMENT` n'est pas posé, après une
  simulation sur la prod (`scripts/rapprocher_rollee.py`).

**Cœur comptable VTC (AXE-831, 802, 803, 804)**
- TVA déductible estimée sur les dépenses venues de la banque, d'après la
  catégorie (AXE-831, #152) : table versionnée
  `packs/tva_deductible.toml` avec sa source (CGI, BOFiP), prudence en cas
  de doute. Reprise des écritures passées TTC par OD :
  `scripts/reprendre_tva_deductible.py`.
- Registre des immobilisations et amortissement linéaire au prorata
  (AXE-802, #154) : dotation 6811/28182 à la clôture, cession, 2033-B et
  2033-C. Le véhicule va en 2182 (et plus en 218). Plafond de l'art. 39-4
  non appliqué (transport de personnes, lecture par analogie, à valider
  AXE-815).
- LOA (AXE-803, #155) : contrat saisi par le chauffeur, premier loyer
  majoré étalé en 486, engagement hors bilan dans la liasse, levée
  d'option = achat en 2182. La LOA va en 612, la LLD reste en 613.
- Bilan d'ouverture d'une société existante, repris de son FEC (AXE-804,
  #131) : lecteur tolérant, garde-fous contre un faux FEC, attestation et
  empreinte, une seule reprise par dossier. Déficits antérieurs saisis, ils
  réduisent l'IS. Saisie guidée sans FEC : pas faite.

**Dossiers et sociétés (AXE-846, 849)**
- Le dirigeant saisit siège, capital et associés (écran « Ma société »),
  pré-remplis depuis Recherche d'entreprises (AXE-846, #125). Corrigé au
  passage : « Oui, c'est bien mon entreprise » échouait en production (droit
  UPDATE du rôle web).
- Registres INSEE (Sirene 3.11) et RNE relus chaque semaine ; un écart avec
  la déclaration du dirigeant bloque clôture et liasse jusqu'à son choix
  (AXE-849, #130). Rien ne tourne sans `INSEE_API_KEY` ou un compte RNE.

**Catégorisation (AXE-732, 816, 871, 887, 888, 900, 901)**
- Mesure du pack VTC sur le premier flux réel (AXE-732, commentaire du
  ticket) : règles 83,6 %, modèle 10,2 %, abstention 6,3 % sur 827
  opérations de MK DRIVING et B'CARS.
- Règles ajoutées (AXE-871, #156) : `POP SVCS`, URSSAF abrégé, cafés et
  boulangeries (repas), pharmacie et tabac (usage personnel probable), ces
  deux dernières en confiance basse. Plancher de 5 € sur les retraits
  d'espèces. Chaque décision humaine garde son **contexte** (libellé,
  montant, proposition, nature) et, depuis AXE-901 (#160), l'avis de
  chaque étage.
- Objectifs V1 mesurés (AXE-816, #159, `scripts/mesurer_objectifs.py`) :
  précision 100 %, règles 83,9 %, recours au LLM 1,9 %, mais **38,4 %
  d'automatique pour 85 % visés**, surtout par conception (recettes en
  attente du rapprochement Rollee, rémunération et repas à confirmer).
  Décision à prendre : AXE-905.
- Part de chaque étage et délai opération → écriture suivis chaque jour en
  production (AXE-900, #161, doc 15 §2).
- **L'IA** : démo avec propositions calculées à l'avance (AXE-888, #153),
  puis étage LLM dans la synchro par l'API Batch (AXE-887, #164) : il
  propose, n'impute jamais. Budget de 0,50 $ par chauffeur et 100 $ au
  global par mois, réservé avant l'envoi ; coupe-circuit, idempotence,
  pseudonymisation bloquante. Les alertes vont à l'équipe AxeL (Sentry) ;
  le gestionnaire voit le nombre de libellés, jamais le coût. **Éteint
  par défaut** (`AXELCOMPTA_LLM_ACTIF`).
- Modèle de catégorisation dans un bucket S3 privé, versionné, empreinte
  vérifiée au téléchargement (AXE-847, #126). Louis a confirmé le 12/11
  que le modèle v2 y est (AXE-830).

**Interface, juridique, exploitation**
- Refonte visuelle (AXE-873, #137 à #151) : design system v2.0
  monochrome ([ADR-008](adr/ADR-008-design-system-monochrome.md),
  [DESIGN.md](../DESIGN.md)), barre latérale claire, nouvelles primitives
  (Select, Tabs, Table, Toast, Dialogue), tous les écrans repris. Avant,
  AXE-870 (#129) avait remis le design system et le code d'accord.
- Textes juridiques rédigés d'après les services réellement branchés
  ([juridique/](juridique/README.md)), affichés dans l'app sur
  `/legal/…` (AXE-859, #128). 20 blancs « À COMPLÉTER » et la relecture
  juriste restent dans AXE-813.
- Banc de performance sur les 28 routes de lecture du front, par profil
  (AXE-843, #127) : tout sous la cible en local. Le préchauffage prend
  ~3 s par dossier. La mesure en production reste à faire.
- Fichiers `demo_*` du chemin de production renommés (AXE-840, #162) :
  `api/routes.py`, `api/auth.py`, `comptes.py`…
- AXE-768 fermé (AXE-420 et AXE-424 faits).

### Fait du 2026-11-05 au 2026-11-10 (PR #87 à #123)

**Grand livre et invariants du doc 06**
- I4 (AXE-806, #91) : aucune écriture datée dans un exercice clos, refusée
  en base par trigger. Une correction d'exercice clos est datée du premier
  jour de l'exercice ouvert du dossier (AXE-838, #103). Une opération
  bancaire tardive dans un exercice clos part en quarantaine.
- I3 et I7 (AXE-807, #92) : numérotation continue par dossier et par
  exercice, posée par trigger dans la transaction ; contrôle quotidien de la
  balance (3 h), alerte Sentry et métrique `balance_desequilibree_total`,
  sans correction automatique.
- Décisions humaines au grand livre (AXE-420, #93) : chaque décision écrit
  une OD de reclassement `{S}:decision-{k}` du compte en vigueur vers le
  nouveau ; annulation = retour en 471. Décision et OD dans la même
  transaction (AXE-852, #114). Reprise des décisions d'avant :
  `scripts/materialiser_decisions.py`.
- Quarantaine d'ingestion résolue par le gestionnaire (AXE-424, #97) :
  accepter un montant modifié (contre-passation puis nouveau montant),
  ignorer ; écran « Opérations bancaires à revoir » dans Anomalies.
- Un sous-compte 512 par compte bancaire (5121, 5122…) et solde comptable
  face au solde de la banque (AXE-832, #87).
- Libellés d'écritures sans la catégorie entre parenthèses (AXE-848, #118).

**TVA (AXE-805, #121)**
- CA3 de chaque période (mensuelle ou trimestrielle), échéance, écriture de
  liquidation vers 44551 ou 44567, déclaration avec preuve. La CA3 annuelle
  de la liasse reprend la somme des périodes. Rappels J-7 et J-2. Écran
  « Ma TVA » côté chauffeur.

**Mode expert et responsabilité juridique (AXE-800, #120)**
- Rôle `expert_comptable` habilité par un admin (cabinet, Ordre, lettre de
  mission, dossiers couverts) ; engagement de responsabilité versionné ;
  motif obligatoire sur chaque imputation, annulation et qualification. Le
  mode expert, les anomalies, les opérations classées et la quarantaine lui
  sont réservés. Le chauffeur voit « Reclassée par [nom], expert-comptable ».
- Opérations déjà classées : filtres, verdicts « juste » / « faux »
  (AXE-823, #99) ; moyen de paiement affiché (AXE-855, #117).
- Performance (AXE-824, #100) : index et cache de la file expert ; à 200
  dossiers × 300 écritures, file expert 11,5 s → 0,14 s.

**Catégorisation et anomalies**
- Ordre du pipeline : virements internes, règles du pack, modèle, puis
  catégorie de la banque (Bridge) en simple proposition ; 7 règles VTC
  ajoutées (AXE-826, #88). Sans modèle ML, MK DRIVING passe de 18 % à 56 %
  d'opérations classées seules, B'CARS de 6 % à 44 %.
- Sans modèle de catégorisation, la synchro s'arrête et le dit (AXE-825,
  #111) ; repli sur les règles seules avec `AXELCOMPTA_SANS_MODELE=1`.
- Plancher réglable par règle : sous 5 €, la règle carburant propose sans
  imputer (AXE-837, #106).
- Retraits d'espèces : une question dédiée au chauffeur (AXE-844, #108).
- Qualifications d'anomalies en base, avec historique (AXE-814, #98) ;
  détecteurs carburant affinés et moyen de paiement sous chaque alerte
  (AXE-836, #107).

**Dossiers et onboarding**
- Création des dossiers en masse depuis un CSV, avec rapport ligne par
  ligne avant création (AXE-809, #95).
- L'import pose l'exercice, la forme et l'activité depuis Sirene (AXE-834,
  #89) ; le chauffeur confirme sa configuration, et clôture et liasse
  l'attendent (AXE-730, #109).
- Comptes bancaires retenus, écartés ou à décider (AXE-729, #110) ; le
  gestionnaire voit ceux qui attendent un choix (AXE-851, #113).
- Nouveaux chauffeurs Digifactory proposés dans Entreprises, bouton
  « Synchroniser » exécuté par le worker (AXE-845, #105).
- Tags d'entreprises et exclusion des traitements (AXE-829, #90).
- Rappels envoyés par le SMTP ou le fournisseur SMS du gestionnaire,
  paramètres chiffrés, lien de désinscription (AXE-808, #122).

**Sécurité, production et qualité**
- MFA native de Supabase demandée à l'admin et à l'expert-comptable
  (jeton `aal2`), journal des connexions et des exports, « Accès à votre
  dossier » pour le dirigeant (AXE-812, #101). `tenants/mfa.py` retiré.
- Production isolée (AXE-810, #94) : `/metrics` fermé sans
  `METRICS_TOKEN`, verrous du rôle web testés.
- Compte de test en lecture seule qui ouvre l'espace chauffeur de tout
  dossier du portefeuille, avec date de fin et trace d'audit (AXE-822,
  #119, #123).
- Erreurs métier en 4xx avec leur phrase, jamais 500 (AXE-839, #104 ;
  AXE-853, #116). Une seule tête Alembic en CI, l'API refuse une base en
  retard (AXE-841, #102, #112) ; le test des migrations compare tout le
  schéma au modèle ORM (AXE-854, #115).

### Fait du 2026-09-27 au 2026-11-05 (PR #41 à #86)

**Liasse et exports (AXE-438, AXE-422, AXE-557, AXE-558 ; 14-15/10 et 24-25/10)**
- La liasse est contrôlée avant d'être livrée : équilibre, résultat,
  totaux, contrôles inter-cases (`test_controles_tdfc`).
- CA3 calculée en centimes et rangée dans la liasse pivot.
- Réel normal (`regime_liasse = "2050"`) : bilan 2050/2051, compte de
  résultat 2052/2053, totaux 2054, 2055, 2056, 2058-A et 2058-B, repris des
  mêmes chiffres que la 2033. Pas de PDF CERFA 2050, pas de lignes de
  détail. La 2033 reste la liasse par défaut.
- CCA et FNP : le chauffeur saisit le montant, le compte et le libellé ;
  l'estimation entre dans la liasse, le FEC et l'aperçu de clôture
  (`provisions_cloture`). Le moteur ne décide jamais seul d'une provision.
- FEC : validateur A.47 A-1 (colonnes, dates, équilibre). Il reste un
  fichier texte, affiché « FEC » à l'écran. Toujours pas passé dans Test
  Compta Demat (outil Windows de la DGFiP).
- Une case à zéro reste vide sur les formulaires et les exports ; le FEC
  garde `0,00`.
- Bilan simplifié équilibré avec le capital (101x) et les immobilisations
  (2x) (AXE-421).
- Amendes : le calcul était déjà juste (CGI art. 39-2), verrouillé par un
  test (AXE-559).
- Reste sur AXE-484 (priorité basse) : lignes de détail du 2054, 2057,
  2058-C, 2059, Test Compta Demat.

**Modules V1 posés (23-25/10)**
- `anomaly/` (AXE-437) : profil par dossier et détecteurs V1 (personnel,
  enseigne ambiguë, écart 3σ, doublon de pièce, double plein). Le
  gestionnaire qualifie une alerte sur `/anomalies/{dossier}`.
  Les qualifications, d'abord en mémoire de process, sont en base depuis
  le 06/11 (AXE-814).
- `documents/` (AXE-425) : les photos de justificatifs sont en base
  (`justificatifs`), par tenant et dossier, avec empreinte, 8 Mo max, RLS.
  La photo n'est toujours pas lue (pas d'OCR).
- `pseudonymize/` (AXE-436) : seule porte vers un LLM. Un prompt qui
  contient encore un IBAN, un e-mail, un téléphone, une carte, une plaque,
  un NIR ou un nom connu du dossier est refusé. `LLMProvider` n'accepte que
  ce type. **Aucun fournisseur LLM n'est branché.**
- `jobs/` et `tenants/mfa.py` (AXE-442) : file de jobs Postgres
  (`FOR UPDATE SKIP LOCKED`, ADR-002), TOTP RFC 6238, rôles lecture,
  membre, admin. La file de jobs sert depuis le 09/11 au worker (import des
  dossiers, « Synchroniser », rappels). Le TOTP maison a été remplacé par
  la MFA native de Supabase le 09/11 (AXE-812).
- Observabilité (AXE-426) : `GET /metrics` (Prometheus), journal JSON,
  Sentry s'il y a un DSN (vide en local).
- `api.app` est le point d'entrée (`uvicorn axelcompta.api.app:app`, AXE-428)
  avec `GET /sante`. Les routes vivent dans `api/routes.py` (AXE-840) : la
  migration route par route vers les façades reste à faire.

**Gestionnaire**
- Mode expert (AXE-560, puis AXE-694/695) : file de tout ce qui est à
  traiter, tous dossiers confondus, 50 par page, filtres. « Imputer »
  annonce qu'il écrit en comptabilité, contre-passe l'écriture d'origine,
  et s'annule.
- Entreprises (AXE-561, AXE-696/697) : filtres par étape restante, état
  dans l'URL, tri, pagination à 25, fiche qui reste à l'écran, dossiers
  retirés qui se restaurent.
- Rôles appliqués dans l'interface (AXE-701) : le rôle Lecture ne voit pas
  les actions d'écriture ; retirer un membre pose le rôle `retire`.
- Invitations (AXE-702) : en masse, renvoi, annulation.
- Rappels (AXE-698/699) : plus de doublons de règles préfaites, règles
  suspendables, un seul vocabulaire de relance. L'envoi hors de
  l'application est branché depuis le 10/11 (AXE-808).
- Anomalies accessibles depuis le mode expert (AXE-700), navigation et
  focus clavier (AXE-703).

**Chauffeur**
- Ticket : une photo vise une seule dépense, nommée avant l'envoi (AXE-483).
- Squelettes de chargement, blocs remplis dans l'ordre d'arrivée (AXE-562).
- Correctifs de la revue UX d'Arthur (AXE-704, 05/11) : un seul « résultat
  à ce jour » (AXE-688), écran Exercice dans l'ordre avec étapes bloquées
  tant qu'il reste à traiter, et l'API refuse la liasse et la signature
  greffe dans ce cas (AXE-687), cloche bornée avec un lien par type
  (AXE-691), cibles de 44 px et contrastes AA (AXE-692), langage en effets
  plutôt qu'en codes (AXE-689), erreurs d'authentification en français
  (AXE-693), À traiter avec une carte à la fois, un compteur et « Annuler »
  (AXE-686, #81).

**Performance (Arthur, 31/10, mergé le 04/11)**
- Le pipeline garde son résultat par (libellé, montant) ; Exercice et
  Compte ne chargent plus les opérations (AXE-565).
- La file expert ne calcule plus de propositions et lit chaque dossier une
  fois (AXE-567).
- Agrégats du portefeuille en base (`agregats_dossier`, invalidés par
  triggers, migration `e7b3d9a15c42`) : la page Entreprises ne reconstruit
  plus chaque dossier (AXE-566).

### Passage en mode réel (05/11)

Serenity a ses premiers chauffeurs sur Digifactory (13 contacts, dont 7
nouveaux). La base Supabase devient la base réelle du portefeuille ; le
menu Démo et les faux comptes sont retirés ; Karim, Yanis et
`demo@axelcompta.fr` sont supprimés, puis Sophie : plus aucune donnée ni
compte de démo en base.
Détail : [doc 17](17-plan-demo-backend.md). Le lien avec Rollee devient
nécessaire pour les recettes des vrais chauffeurs. Tickets ouverts le même
jour, dans l'ordre :
- AXE-817 (urgent) : contrat, sandbox et choix entre User API et Company API ;
- AXE-818 : client API et `RolleeProvider` ;
- AXE-819 : le chauffeur relie ses comptes Uber et Bolt via Rollee Connect ;
- AXE-820 : webhooks signés et synchro quotidienne de secours ;
- AXE-821 : revenus Rollee réconciliés avec le virement Digifactory, puis
  écritures 706, TVA et commission.

Les relevés CSV (AXE-801) restent la source de secours pour un chauffeur
sans Rollee. Les cinq tickets Rollee sont faits depuis le 12/11 (PR #132 à
#136).

### En cours (13/11)

- AXE-842 : appliquer en production tout ce qui est mergé depuis le 05/11
  (voir l'alerte en tête). Décision de Louis du 06/11 : étape par étape,
  chaque reprise en simulation, puis appliquée après accord.
- Vérifications sur de vraies données, une par PR : test de contrat Rollee
  en sandbox (unité des montants, signature des webhooks), lecture d'un
  vrai SIREN à l'INSEE et au RNE, un vrai FEC repris, simulation du
  rapprochement Rollee sur la prod (AXE-911).

### Prévu

**Novembre — confiance client : un mois réel exporté** (AXE-767, urgent).
Fait : AXE-726, 727, 729, 730, 732, 768, les contre-passations AXE-420 et
AXE-424, et tout le cœur VTC ci-dessus. Reste, dans l'ordre :

1. AXE-842 : production à jour, puis AXE-850 : reprendre les écritures
   restées au 471 après la synchro sans modèle du 05/11.
2. AXE-728 : première synchro et bulletin de connexion des chauffeurs réels.
3. Brancher Rollee en production : branchement, chauffeurs reliés, relevés
   rapprochés. AXE-801 (relevés CSV Uber et Bolt) reste le secours pour un
   chauffeur sans Rollee ; il réutilisera la même OD de ventilation.
4. **AXE-733 (le jalon)** : un mois d'un dossier réel, tranché, équilibré,
   exporté.

**Décembre — prod fiable au 31/12** (AXE-770, échéance 15/12)
- AXE-427 : branche prod et déploiement continu.
- AXE-811 : hébergement de production (ADR-003) et restauration
  chronométrée. Les webhooks Rollee l'attendent (adresse publique).
- AXE-441 : décider du périmètre de la signature qualifiée RGS (devis
  Yousign/Docusign, ADR-004), puis le circuit clôture → archive.

**Catégorisation, après le mois réel**
- AXE-902 : geler le jeu de test (dépend d'AXE-423).
- AXE-904 : recalibrer le modèle sur les décisions réelles, le promouvoir
  seulement s'il fait mieux sur le jeu gelé ; avec lui, le top 3 du modèle
  dans l'entrée du LLM.
- AXE-903 : mesurer le rappel de la détection d'anomalies.
- AXE-912 : débloquer un versement de plateforme « à vérifier ».

**Après, ou à trancher**
- AXE-423 : finir l'audit du dataset 10 ans. La relecture des 500 lignes
  (ancien J1) en est toujours à 7/500.
- AXE-833 : reprendre les mois d'avant la connexion Digifactory.
- AXE-433 : connexion bancaire directe par le chauffeur (basse priorité).
- AXE-484 : annexes 2054 à 2059 en détail et Test Compta Demat (basse).
- AXE-765 : connecter Qonto et un accès dédié pour le bot Finance & Admin.

### Plan V1 de l'analyse critique du 2026-11-05 : où on en est

Une relecture du plan contre les docs 01, 02, 06, 10 et 14 avait montré
des trous que Linear ne couvrait pas (72 points ajoutés à P-AXE-28).

**Fait** : AXE-800 (mode expert et responsabilité de l'expert-comptable),
AXE-802 (immobilisations), AXE-803 (LOA), AXE-804 (bilan d'ouverture),
AXE-805 (TVA en cours d'année), AXE-806 (I4), AXE-807 (I3 et I7), AXE-808
(rappels par e-mail et SMS), AXE-809 (création en masse), AXE-810
(isolation de la production), AXE-812 (MFA et journal des accès), AXE-814
(qualifications d'anomalies en base), AXE-816 (mesure des objectifs V1,
sur une référence provisoire). Détail plus haut.

**Reste à faire**
- AXE-801 : versements Uber/Bolt depuis les relevés CSV (secours de
  Rollee).
- Production : AXE-811 (hébergement et restauration), AXE-813 (CGU/CGV, DPA
  et engagement de l'expert-comptable relus par un juriste ; les textes
  sont rédigés, AXE-859).
- Calendrier : AXE-815 (relecture par un expert-comptable **avant le
  31/01/2027** ; les liasses 2026 partent en mai 2027). Elle doit couvrir
  les choix pris cette semaine : table de TVA déductible, plafond de
  l'art. 39-4 non appliqué au VTC, comptes du pack.

### Décisions à prendre (ouvertes dans Linear)

- AXE-905 : le taux automatique mesuré à 38 % pour 85 % visés. Compter
  comme automatiques les recettes imputées par le rapprochement Rollee ?
  Imputer seule la rémunération du dirigeant ? Accepter que les repas
  restent à confirmer ?
- AXE-766 : valider la définition de « fini » pour novembre (un mois réel
  exporté et l'UX P0, pas tout le polish) et pour décembre (déploiement
  continu et décision RGS), et arbitrer ce qui glisse en T1 2027.
- Offboarding (doc 14 §2 : export et purge d'un tenant, RGPD) : aucun
  ticket. À décider s'il fait partie de la V1 ou du contrat (AXE-813).

### Actions hors code (Louis)

- Poser une limite de dépense dans la console Anthropic, une clé par
  environnement, avant `AXELCOMPTA_LLM_ACTIF=1`.
- Faire valider par un expert-comptable la référence de 68 libellés qui a
  servi au banc de l'IA, puis relancer le banc.
- Créer la clé Sirene 3.11 et le compte RNE (AXE-849).
- Lancer la simulation du rapprochement Rollee sur la prod et poser le
  bilan sur AXE-911.

### Ce qui reste vrai de septembre

- Expert-comptable : reporté « tout à la fin » le 26/09 ; depuis le 05/11,
  calé avant le 31/01/2027 (AXE-815). D'ici là, la table comptes →
  rubriques suit la notice, sans relecture professionnelle.
- Tous les statuts sont codés (SASU, SAS, EURL, SARL, EI ; IS, IR, option
  IR ; franchise ou réel de TVA). Micro-entreprise non faite.
- La clôture est décidée par le chauffeur, et par lui seul. Le gestionnaire
  ne voit que des agrégats.
- Pas de SMTP chez AxeLCompta : la cloche est le canal, e-mail et SMS
  sont des intégrations du gestionnaire (branchées le 10/11, AXE-808 ;
  plusieurs par type depuis le 12/11, AXE-872).
- À lancer en attente externe : devis de signature RGS, trame CGU/CGV/DPA.

## Vue d'ensemble des phases

```mermaid
gantt
    dateFormat  YYYY-MM
    title Trajectoire AxeLCompta (ordres de grandeur d'août, non recalés)
    section Phase 0 — Cadrage
    Validation docs, juridique, données   :p0, 2026-06, 2M
    section Phase 1 — Fondations
    Socle technique + ingestion + ledger  :p1, 2026-08, 4M
    section Phase 2 — Intelligence
    Pipeline règles/ML/LLM + anomalies    :p2, 2026-11, 4M
    section Phase 3 — Production comptable
    Clôture, liasses, FEC, signature      :p3, 2027-02, 4M
    section Phase 4 — Pilote client
    Pilote client, A/B, durcissement      :p4, 2027-05, 3M
    section Phase 5 — Cible
    Partenaire EDI, INPI API, scale       :p5, 2027-08, 6M
```

Jalon de fin de phase = démo + revue de la check-list de phase. On ne commence pas
la phase suivante avec des invariants non tenus.

---

## Phase 0 — Cadrage et dé-risquage (AVANT d'écrire du code produit)

### 0.1 Décisions et juridique
- [x] ~~Relecture/amendement de toute cette documentation par Louis + associé.~~
      **Annulé (2026-09-07)** : l'associé n'est plus sur ce produit —
      segmentation actée le week-end du 2026-09-05/06. Louis seul sur le
      produit (voir hypothèse de capacité en tête de doc). **Louis avait
      déjà relu (2026-09-02)** ; la condition du README avant "code produit"
      est donc satisfaite côté relecture — plus d'associé à attendre. Sujet
      clos, ne pas rouvrir.
- [x] Structure du pilote confirmée : 1 gestionnaire → ~200 dossiers indépendants, mix SASU/EURL à l'IS + quelques option IR.
      ~~Collecter la liste exacte statut par chauffeur~~ **Annulé le
      2026-09-26** : tous les formats seront codés, le statut se renseigne
      dossier par dossier à la création (voir J2 dans le recalage).
- [x] Positionnement éditeur validé (doc 02 §2.3).
- [x] CGU/CGV + DPA rédigés (trame au moins). **Fait le 2026-11-11 (AXE-859)** : `docs/juridique/`, affichés sur `/legal/…`. Restent 20 blancs « À COMPLÉTER », la relecture juriste, l'acceptation tracée et le DPA signé (AXE-813).
- [x] Token Digifactory fonctionnel — **débloqué le 2026-09-11** (doc 16
      §7) : mauvais type d'en-tête depuis le début (`Authorization: Bearer`
      au lieu de `X_DIGI_TOKEN`, spec initiale erronée du fournisseur, rien
      de cassé côté client). Les 4 routes (`/contacts`, `/categories`,
      `/accounts`, `/transactions`) répondent 200 en réel. Chemin A
      implémenté et testé en réel (`DigifactoryHttpClient`, doc 16 §7/§9
      point 1). Reste : brancher ce client sur `fetch_transactions` —
      bloqué sur la table `contact_nr → dossier_id` (doc 16 §9 point 5),
      pas un problème technique : dépend de l'arrivée des chauffeurs chez
      Digifactory (voir J3 dans le recalage).
- [ ] Contrat Bridge direct : pricing, volumes, statut, sandbox — piste parallèle non bloquante, testée après le pilote Digifactory (doc 16 §8).
- [x] Contrat Rollee : conditions fleet mode, volumes, API sandbox, pricing. **AXE-817 fermé le 2026-11-12** : accès par le compte Rollee de Serenity, API utilisateur (le chauffeur relie ses comptes dans Rollee Connect).
- [ ] Choix prestataire signature (ADR-004) — devis Yousign/Docusign. **Précisé (2026-09-11, doc 20 §4)** : le dépôt des comptes annuels au greffe (INPI) exige spécifiquement une signature électronique **avancée avec certificat qualifié RGS** (C. com. art. R.123-5) — à vérifier explicitement dans le devis retenu, pas n'importe quel niveau de signature électronique.
- [ ] Décision hébergement prod (ADR-003) après premier échange sécurité banque.
- [ ] **Écrire les ADR 001-006** (docs/adr/) — templates disponibles, à valider.

### 0.2 Les données (chemin critique — démarrer immédiatement)
- [x] Récupérer un échantillon des 10 ans d'historique.
- [x] **Vérifier le risque n° 1** : le lien libellé bancaire ↔ imputation existe-t-il ? (doc 07 §2.1) — **fait (2026-09-02)** : lien structurel fiable à 100% côté FEC historique, lien sémantique plus faible sur les paiements carte génériques. Détail : `_AUDIT_DONNEES/rapport_audit_dataset.md` §2.
- [x] Rapport d'audit du dataset (formats, volume, qualité des labels, droits) — **fait (2026-09-02)**, brouillon Claude non relu par Louis ni un comptable (`_AUDIT_DONNEES/rapport_audit_dataset.md`).
- [x] Construire la taxonomie du **pack VTC** (~40-80 classes) avec le comptable du client — structurée comme un pack métier dès le départ (doc 03 §3bis). **Fait (2026-09-02) côté brouillon algorithmique** (`_AUDIT_DONNEES/packs_vtc/taxonomie.md`, 30 catégories) — **pas encore fait avec le comptable du client**, c'est l'écart réel derrière cette case.
- [x] Table de mapping comptes historiques → taxonomie — **fait (2026-09-02)**, brouillon (`_AUDIT_DONNEES/packs_vtc/mapping_pcg_categorie.csv`), même réserve que ci-dessus.
- [ ] 500 lignes relues à la main = premier jeu de test gelé. Échantillon
      généré (`_AUDIT_DONNEES/resultats/echantillon_500_a_relire.csv`),
      **7/500 relues au 2026-11-05** (inchangé depuis le 21/09, AXE-423), outillage prêt
      (`relecture_rapide.py`, pré-passe qui réduit à ~200 lignes à regarder).
      Prévu le week-end du 2026-09-12/13, **non fait** ; nouvelle cible dans le
      recalage ci-dessous.

### 0.3 Spike techniques (timeboxés, 2-3 jours chacun)
- [x] Spike Digifactory : premier appel réussi — **fait le 2026-09-11** (doc 16 §7), les 4 routes en 200 réel. `/contacts` expose `siren`/`siret`/`vatno` en champs distincts (Pierre a corrigé le même jour un champ `siret` à double usage repéré lors du premier test, doc 16 §3.3) ; au moins un contact sans aucun des trois dans l'échantillon, confirmant qu'il faut une table de correspondance explicite. Poids réel mesuré : ~807 Ko/2029 transactions pour un seul contact sans filtre `since` (doc 16 §5) — confirme qu'un chargement initial sur 200 dossiers doit être découpé, pas lancé tel quel.
- [ ] Spike Bridge sandbox direct : connexion, récupération transactions, webhooks — piste parallèle non bloquante, après stabilisation du canal Digifactory (doc 16 §8).
- [x] Spike baseline ML : TF-IDF + régression logistique sur le même échantillon — **fait (2026-09-02)**, 79,5% d'exactitude sur dossiers jamais vus (`_AUDIT_DONNEES/rapport_audit_dataset.md` §6). **Écart avec ADR-007 tranché (2026-09-21)** : le 94,4% venait du token compte PCG, absent à l'inférence (mesure refaite : 96,3% avec le token, 79,5% sans). ADR-007 amendé, chiffre de référence 79,5%. Reste ouverte la vraie mesure de précision, qui dépend des 500 lignes relues (§0.2). Le spike d'origine n'est plus dans le repo, donc le classement sentence-transformers/CamemBERT est invérifiable ; volet embeddings non fait, à rouvrir seulement si les 500 lignes montrent une précision insuffisante.
- [ ] Spike OCR : 30 tickets réels dans Tesseract vs PaddleOCR vs Vision LLM (ADR-005).
- [ ] Spike FEC : générer un FEC minimal et le passer dans « Test Compta Demat ».
- [ ] Maquettes Figma des 3 écrans clés (doc 11 §3) + retours de 2 utilisateurs cibles.

**Critère de sortie Phase 0** : dataset audité, baseline ML mesurée, Digifactory
testé (ou développement mené contre fixtures si le token reste bloqué — doc 16
§7), décisions ADR 001-005 actées, docs validées.

---

## Phase 1 — Fondations (socle + ingestion + cœur comptable)

### 1.1 Socle technique
- [ ] Monorepo (backend + front), Docker Compose dev (Postgres, MinIO).
- [ ] CI complète dès le premier jour (doc 08 §4) — la barrière avant le code, pas après.
- [ ] `core/` : Money (centimes), Result, erreurs, identifiants typés + tests de propriétés.
- [x] Multi-tenant : modèles tenant (mode portefeuille/mono) + dossier — **fait**. RLS, middleware d'isolation + suite de tests d'isolation — **posés le 2026-09-22** (doc 03 §7, migration `87fc7238e52e`), sur le schéma de démo actuel. Reste pour le vrai V1 : étendre aux tables futures au fur et à mesure qu'elles apparaissent (chaque nouvelle table dossier-scopée doit recevoir sa policy dans la même migration qui la crée, pas après coup).
- [x] **Configuration de dossier de premier rang** : statut juridique + régime fiscal + régime TVA + pack métier, matrice doc 06 §7 en données versionnées (toutes les colonnes dans le modèle, IS et option IR opérationnelles). Chaque dossier indépendant, valeurs tenant en simple pré-remplissage.
      **Fait le 2026-09-26** : `tenants/matrice_statuts.toml` + `statuts.py`,
      formes SASU, SAS, EURL, SARL, EI et régimes IS, option_IR, IR, micro,
      TVA réel normal, réel simplifié (avant 2027) et franchise, pack métier,
      année de début d'option IR. Validation à chaque écriture de dossier.
      Le moteur lit la matrice : compte d'usage personnel (455, 108, ou
      signalé sans écriture), IS seulement pour la colonne à l'IS, 2065 et
      dépôt au greffe refusés (409) hors de leur colonne. Reste : la liasse
      2031 (IR), la 2050 (réel normal), la franchise dans la clôture, puis
      les alertes et la bascule de fin d'option IR (item suivant).
- [x] **Option IR bornée** : date de début d'option, décompte des 5 exercices, alertes N-1/N, bascule IS tracée (doc 06 §7) + changement de régime par avenant daté (mécanique générique).
      **Fait le 2026-09-26** : `tenants/avenants.py`, table append-only
      `avenants_regime` (verrou en base, policy par dossier, migration
      `a4d7e2c9b518`). Alertes calculées à l'avant-dernier et au dernier
      exercice, affichées au chauffeur (écran Exercice) et au gestionnaire
      (portefeuille). Au dernier exercice, le cron horaire enregistre seul
      l'avenant « fin d'option IR » vers l'IS à l'exercice suivant,
      visible avant de s'appliquer ; `regime_pour_exercice` donne le régime
      de n'importe quel exercice. Restent : la renonciation anticipée côté
      écran (le motif existe, pas le parcours, à décider avec Louis car
      c'est un acte irrévocable du dirigeant), et le passage d'un exercice
      au suivant, qui n'existe pas encore dans le code (un dossier n'a
      qu'un exercice) et devra lire `regime_pour_exercice`.
- [x] **Création de dossiers en masse** : import CSV/XLSX de la configuration (SIREN, forme, régime, dates d'exercice, option IR…) pour onboarder 200 dossiers sans 200 saisies manuelles, avec rapport de validation avant création.
- [x] Auth B2B : email + MFA TOTP, rôles V1, journal d'audit append-only. **Tranche journal (2026-09-24)** : décisions et signatures seulement (`journal_audit`). Auth/MFA et le journal consultations/exports restent ouverts. **Posés le 2026-10-25 (AXE-442)** : TOTP RFC 6238 (`tenants/mfa.py`) et rôles lecture/membre/admin, appliqués dans l'interface gestionnaire le 2026-11-04 (AXE-701). Le TOTP n'est pas encore demandé à la connexion ; connexion, export et consultation ne sont pas encore journalisés. **Fait le 2026-11-09 (AXE-812)** : MFA native de Supabase demandée à la connexion (admin et expert-comptable), connexions et exports journalisés.
- [x] Observabilité : logs JSON structurés, Sentry, premières métriques. **Fait le 2026-10-25 (AXE-426)** : `GET /metrics` Prometheus, journal JSON, Sentry si `SENTRY_DSN` est posé. Restent les dashboards et l'alerting (doc 15).

### 1.2 Ingestion
- [ ] Archivage brut immuable (hash, horodatage) de tout ce qui entre.
- [ ] **Interface `DataProvider` (ABC)** dans `ingestion/providers/base.py` + types `NormalizedTransaction`, `PlatformSettlement` (doc 13 §2).
- [ ] **`DigifactoryProvider`** (canal actif pour le pilote, doc 16) : contacts/comptes/transactions, sync incrémental sur `since` (pull, pas de webhook), santé des connexions (`paused`/`data_access`/`last_refresh_status`), table de correspondance `contact_nr → dossier_id`, fixtures couvrant les cas doc 16 §9.7.
- [ ] **`BridgeProvider`** direct : piste parallèle non bloquante (sandbox, doc 16 §8), à développer après le pilote Digifactory — items/comptes/transactions, polling + webhooks, santé des connexions, monitoring expiration consentements DSP2.
- [x] **`RolleeProvider`** : connexion fleet mode, endpoints income/trips/wallet, webhooks `wallet.payout_received`, polling daily fallback, monitoring expiration tokens (doc 13 §3). **Fait le 2026-11-12 (AXE-818 à 820)** : client JWT par branchement, revenus par période, webhooks signés (comptes et données prêtes), rattrapage quotidien à 4 h, plateformes « à reconnecter » signalées au chauffeur. Pas vérifié sur de vraies réponses.
- [ ] **`FileImportProvider`** : moteur de profils d'import + parseurs CSV/XLSX/ODS → `RawRow` canonique.
- [x] **Réconciliation `PlatformSettlement` ↔ `NormalizedTransaction`** : algorithme de matching par montant+date+libellé, états (en attente / réconcilié / revue manuelle), alertes trou (doc 13 §4). **Fait le 2026-11-12 (AXE-821)** : OD de ventilation, états `reconcilie`, `en_attente_banque`, `a_classer`, `a_verifier`, `delie`. Sortie de « à vérifier » : AXE-912.
- [ ] **Dashboard consentements** : panneau premier rang listant consentements valides/expirant/expirés pour Digifactory (accès bancaire) et Rollee. Mode relance configurable par tenant (auto ou manuel, doc 14 §2.3) — date d'expiration DSP2 **confirmée exposée côté Digifactory depuis le 2026-09-11** (`item.authentication_expires_at`, doc 16 §3.2/§6). **Classement persisté le 2026-09-24** à chaque synchro (`consentements_bancaires`) : actif / à renouveler (J-14) / expiré / jamais connecté. **Santé de connexion persistée le 2026-09-25** sur la même ligne. **Écran gestionnaire et relances faits le 2026-09-27** pour Digifactory (doc 14 §2.2, §2.3) : relances dans la cloche du chauffeur, pas d'e-mail. **Rollee depuis le 2026-11-12** (AXE-819, AXE-820) : plateforme perdue signalée dans la cloche, « N à reconnecter » sur la fiche ; rappel « reliez vos plateformes » (AXE-890).
- [ ] Normalisation des libellés versionné + tests.
- [ ] Déduplication/idempotence + rapport d'import avec prévisualisation.
- [x] Quarantaine + UI de correction. **Fait le 2026-11-07 (AXE-424)** : le gestionnaire accepte ou ignore, avec contre-passation.
- [ ] Fixtures : un corpus de fichiers par banque rencontrée + corpus de payloads Rollee (vivant, doc 09 §2.2).

### 1.3 Cœur comptable (`ledger`)
- [ ] Plan de comptes PCG embarqué versionné + comptes par dossier + axe analytique.
- [ ] Écritures append-only, partie double, séquences par journal, périodes + verrous (invariants I1-I8 + triggers de protection). **Fait le 2026-09-24 pour I2** : trigger sur les écritures validées, et contre-passation d'une transaction bancaire modifiée ou supprimée après comptabilisation (doc 06). Séquences, périodes et verrou de clôture (I4) restent ouverts. **Fait le 2026-11-06/07** : I4 (AXE-806), I3 numérotation continue et I7 contrôle quotidien de la balance (AXE-807). Reste I8 (Test Compta Demat, AXE-484).
- [ ] Mécanique générique « template + paramètres dossier → écritures équilibrées » (le moteur ne connaît aucun secteur).
- [ ] **Templates pack VTC** (fichiers de données `packs/vtc/`) : carburant (TVA récupération selon véhicule), péage, entretien, LOA (part non déductible), usage personnel (455/108 selon statut), banale charge TTC/HT/TVA.
- [x] **Templates recettes plateformes** : settlement Rollee → 706 + 44571 (10% ou franchise) + 622x + 44566 (TVA commission selon entité Uber/Bolt — doc 13 §5). Config plateformes dans `packs/vtc/platforms.yaml`. **Fait le 2026-11-12 (AXE-821)** : OD de ventilation sur le virement déjà en 706 ; plateformes et régime de TVA de la commission dans `_AUDIT_DONNEES/packs_vtc/plateformes.csv`.
- [x] Immobilisations : fiche, plan d'amortissement linéaire, prorata, cession + tests de propriétés (Σ dotations = base). **Fait le 2026-11-13 (AXE-802)** : registre en ajout seul, dotation à la clôture, cession avec plus ou moins-value. Reprise des immobilisations au bilan d'ouverture : à la main.
- [x] LOA : loyers, part non déductible, suivi hors-bilan, levée d'option. **Fait le 2026-11-13 (AXE-803)** : premier loyer étalé (486), engagement hors bilan, levée d'option en 2182. Part non déductible non réintégrée (transport de personnes, à valider AXE-815).
- [x] Paramétrage TVA par dossier : `tva_recettes_regime` (assujetti_taux_reduit | franchise), régime déclaration (réel normal — cible unique nouveaux dossiers ; réel simplifié en lecture d'historique seulement, supprimé au 01/01/2027, doc 02 §7bis), surveillance des seuils franchise. Table de règles fiscales versionnée par millésime.
      **Fait le 2026-09-26** : les deux régimes et leur cohérence sont
      validés par la matrice des statuts (`tenants/statuts.py`, le réel
      simplifié refusé pour un exercice ouvert en 2027). Seuils de la
      franchise en base versionnés par millésime
      (`tenants/seuils_franchise_tva.toml`, source
      BOI-TVA-DECLA-40-10-10-20260701 : 37 500 € et 41 250 € pour les
      services en 2025 et 2026), surveillés par `tenants/franchise_tva.py`
      sur le 706 de l'année civile : alerte à 90 % du seuil, perte au
      1er janvier suivant au-delà du seuil de base, perte immédiate
      au-delà du majoré. Affichée au chauffeur et au gestionnaire. Restent :
      la date de début d'activité pour le prorata de la première année
      (le calcul l'accepte, le dossier ne la porte pas encore), et le
      passage effectif au réel, qui attend le passage d'un exercice au
      suivant.
- [ ] Rapprochement bancaire. **Avancé le 2026-11-06 (AXE-832)** : un sous-compte 512x par compte bancaire, solde comptable et solde de la banque côte à côte, écart en rouge. Pas de lettrage ligne à ligne.
- [ ] Dossiers de référence synthétiques → golden tests : SASU IS + Rollee settlements, EURL option IR, dossier franchise TVA, dossier traversant fin d'option IR.
- [ ] **Relecture des templates par un expert-comptable** (prestation, doc 09 §8) — obligatoire avant V1.

### 1.4 Front (en parallèle)
- [ ] Design system de base (tokens, composants, Storybook). Tokens et composants faits ([DESIGN.md](../DESIGN.md)) ; pas de Storybook.
- [x] Design : refonte AXE-873 (design system v2.0, ADR-008). **Fait le 2026-11-11** : primitives AXE-875 et AXE-876, barre latérale AXE-877, tous les écrans AXE-878 à AXE-885 (PR #137 à #151).
- [ ] Écrans : connexion/MFA, dashboard, liste/fiche dossier, transactions, import avec prévisualisation, journaux/balance (lecture).

**Critère de sortie Phase 1** : un fichier CSV réel importé → écritures manuellement
validées → balance équilibrée et FEC brut généré, le tout démontré sur staging,
couverture ledger ≥ 95 %.

---

## Phase 2 — Intelligence (catégorisation + anomalies)

### 2.1 Règles dures
- [ ] Moteur de règles déclaratives 3 niveaux (système/tenant/dossier) + priorités + journal de collisions.
- [ ] Règles avec tests embarqués obligatoires, exécutés en CI.
- [ ] Premier référentiel : ~100-200 règles système du pack VTC (enseignes carburant, péages, plateformes, assurances…) construites depuis le dataset historique.
- [ ] UI de gestion des règles + création assistée depuis une correction.

### 2.2 ML
- [ ] Pipeline de données : dataset versionné, splits par dossier ET période, pseudonymisation.
- [ ] Baseline (TF-IDF + LogReg) → rapport d'évaluation (doc 07 §4).
- [ ] Challenger LightGBM features mixtes ; calibration isotonic ; seuils par classe.
- [ ] Registry de modèles (table + artefacts S3), promotion champion/candidat, rollback. **Artefacts faits le 2026-11-11 (AXE-847)** : bucket S3 privé, un dossier par version, empreinte vérifiée, version choisie par `AXELCOMPTA_MODELE_VERSION`. Pas de promotion automatique (AXE-904).
- [ ] Intégration runtime : chargement champion, prédiction, explication (top features).
- [ ] Jeu des pièges construit à la main + jeu de test gelé.
- [ ] Monitoring de dérive (taux de correction par classe, confiances).

### 2.3 LLM
- [x] **Module de pseudonymisation + tests de fuite bloquants** (doc 10 §4) — avant le premier appel réel. **Fait le 2026-10-25 (AXE-436)** : `pseudonymize/`, `tests/pseudonymize/test_fuite.py`.
- [x] Abstraction LLMProvider (Claude/Gemini/OpenAI), sortie JSON schema contrainte, retry/fallback, cache par libellé-type, budget par tenant. **Interface posée le 2026-10-25** (n'accepte qu'un prompt pseudonymisé ; le LLM seul n'impute jamais). **Claude Fable 5.2 branché le 2026-11-13 (AXE-888, AXE-887)** : API Batch, sortie JSON limitée à la taxonomie, cache par libellé et version du prompt, budget par chauffeur et global, coupe-circuit. Éteint par défaut (`AXELCOMPTA_LLM_ACTIF`).
- [ ] Politique de décision ML×LLM (doc 05 §4) + journalisation des motifs d'escalade. **Avancé le 2026-11-13** : le LLM ne voit que ce que règles et modèle laissent au 471, et n'impute jamais ; chaque décision humaine garde l'avis de chaque étage (AXE-901). Le top 3 du modèle n'est pas encore donné au LLM (AXE-904).

### 2.4 Pipeline assemblé + revue humaine
- [ ] Orchestration 4 étages + auto-validation configurable par tenant.
- [ ] **File de revue** (l'écran clé, doc 11 §3.1) avec raccourcis clavier — **côté indiv, pas gestionnaire, depuis le 2026-09-11 (doc 19 §5.2)**, déclenchée par notification au fil de l'eau plutôt qu'en session groupée. **Existe** : « À traiter » du chauffeur (une carte à la fois, raccourci O, « Annuler », 05/11) et mode expert du gestionnaire (AXE-560). Contre-passations des décisions humaines faites le 07/11 (AXE-420).
- [ ] Boucle de feedback : corrections → labels → réentraînement mensuel → rapport. **Avancé le 2026-11-13** : chaque décision garde son contexte et l'avis de chaque étage (AXE-871, AXE-901) ; seuils sans erreur par catégorie prêts, pas branchés. Réentraînement et promotion : AXE-904.
- [ ] Tests de la matrice de scénarios pipeline (doc 09 §2.3).

### 2.5 Anomalies
- [x] **Profils comportementaux par dossier** (doc 05 §6.2, doc 07 §3.3) — **fait le 2026-10-24 (AXE-437)**, recalculés à la lecture : agrégats incrémentaux par catégorie, construits automatiquement à l'import de l'historique.
- [x] Détecteurs V1 : catégories personnelles, enseigne ambiguë sans/avec ticket incohérent, écart au profil comportemental (3σ), doublons de pièce, double plein. **Fait le 2026-10-24 (AXE-437).**
- [ ] Cycle de vie d'alerte + UI d'instruction (doc 11 §3.2, écart au profil affiché) + templates comptables de résolution (455/108 selon statut du dossier). **UI d'instruction faite le 2026-10-24** (`/anomalies/{dossier}`, ouverte → en instruction → justifiée, usage personnel ou faux positif). Qualifications en base, avec historique, depuis le 2026-11-06 (AXE-814).
- [ ] Jeu d'évaluation : abus historiques connus + abus synthétiques injectés ; mesure rappel/précision.

### 2.6 Justificatifs
- [ ] Stockage WORM, upload UI + adresse email par dossier. **Upload et stockage en base faits le 2026-10-24 (AXE-425)** : table `justificatifs`, par tenant et dossier, empreinte, 8 Mo max, RLS. Pas encore WORM, pas d'adresse e-mail par dossier.
- [ ] Cascade extraction : PDF natif → Factur-X → OCR → Vision LLM, confiance par champ.
- [ ] Matching justificatif↔transaction scoré + file de matching manuel + orphelins.
- [ ] Golden tests OCR (corpus 200 documents annotés).

### 2.7 Accès chauffeur en libre-service (mobile) — cadré dans doc 19, codé pour l'essentiel

> **Au 2026-11-05** : l'espace chauffeur existe (Activité, À traiter, Exercice,
> Mon résultat, Compte, cloche) et a été repris après la revue UX AXE-563.
> Le texte ci-dessous date de septembre ; les items ouverts restent valables.

Contredit le modèle initial : doc 11 §3.3 disait que la page de signature
est « seul écran vu par le chauffeur/gérant » (zéro compte, lien + OTP) ;
doc 04 §4.3 disait que les justificatifs arrivent via le gestionnaire ou par
mail, « vu qu'ils n'ont pas accès à la plateforme ». Louis veut (2026-09-05,
précisé le 2026-09-06) : le chauffeur a son propre compte, relié à ses
propres écritures bancaires, avec une vraie app (mobile) — prend ses tickets
en photo lui-même, répond à des questions de catégorisation simples quand
le système ne sait pas, et peut relier sa propre banque si besoin. **Cadré
et documenté dans [doc 19 — Parcours utilisateur](19-parcours-utilisateur.md)**
(session Claude Code du 2026-09-06) : modèle de compte/onboarding, deux
modes de connexion bancaire par dossier, logique du mode mono-compte. Le
[doc 17](17-plan-demo-backend.md) (plan de démo, pivoté le même jour) en
fait maintenant une des deux interfaces de la démo. Reste à faire : le
code — rien de ceci n'est encore construit. Ne pas confondre avec le flux
Rollee Connect chauffeur (doc 13 §3.3), qui lui est déjà spec depuis le
début.

**Révision structurante du 2026-09-11 (doc 19)** : ce n'est plus juste
« le chauffeur a en plus un accès mobile » — la file de revue, la clôture
et la signature **quittent le gestionnaire pour devenir exclusivement
indiv**. Nouveaux items concrets qui en découlent, aucun encore chiffré :

- [x] **Système de notification** (doc 19 §5.2) : **fait le 2026-09-22,
      internes depuis le 2026-09-26** (décision de Louis : pas de SMTP chez
      nous, la cloche de l'espace chauffeur est le canal ; e-mail et SMS
      sont des intégrations que le gestionnaire branche). Déclenchées par
      `python -m axelcompta.taches` depuis un cron (poste de démo ; serveur
      plus tard, même script). Reste : l'écran d'intégrations du
      gestionnaire (e-mail, SMS), pas décidé.
      Avant : dès qu'une transaction arrive et que le pipeline ne sait pas
      trancher, notifier l'indiv —
      rien n'existait (pas d'email transactionnel, pas de push/in-app).
      Objectif produit : traitement au fil de l'eau, pas une revue de fin
      d'année (répartit aussi notre charge support/LLM sur l'année, doc 09
      §7).
- [x] **Import en masse des invitations** (doc 19 §3.1) : **fait le
      2026-09-22** : `POST /invitations/en-masse` (500 lignes max, résultat
      ligne par ligne, dossiers d'un autre portefeuille traités comme
      inconnus) et un écran de collage/fichier sur le dashboard gestionnaire.
      Le gestionnaire invite ses indivs depuis une base clients, pas seulement
      un par un — distinct du CSV dossiers (§1.1 ci-dessus), **qui reste à
      faire pour le pilote** (pas pour la démo).
      Les invitations partent de Supabase Auth, dont l'envoi était plafonné
      sans SMTP personnalisé : **SMTP configuré le 2026-09-26**, un lot de
      200 invitations peut partir en entier.
- [ ] **Boucle de clôture/complétude bancaire** (doc 19 §5.3, doc 06 §5bis) :
      confirmation de l'indiv + délai de battement + CCA/FNP pour le
      résiduel — la durée du délai et la politique CCA/FNP restent à
      valider avec un expert-comptable, pas tranchées.
- [ ] **Deux signatures distinctes** (doc 20 §4bis) : une validation
      (protège AxeLCompta, pas besoin de qualifié) avant tout envoi, une
      signature légale qualifiée RGS sur le retour des organismes — ne pas
      les traiter comme une seule étape répétée.
- [ ] **Visibilité gestionnaire, confirmation juridique requise** (doc 19
      §2.4, doc 02 §10) : le gestionnaire ne voit que des agrégats tant que
      ce n'est pas confirmé légalement — même « documents déposés : oui/non »
      par dossier est en attente de validation, pas codé par défaut.

**Critère de sortie Phase 2** : sur le dataset historique rejoué, ≥ 85 % de
catégorisation automatique à ≥ 97 % de précision, rappel anomalies ≥ 80 %,
zéro fuite au test de pseudonymisation.

---

## Phase 3 — Production comptable complète

- [ ] Checklist de clôture automatisée (doc 06 §5) : CCA/FNP assistées, cadrage TVA, dotations, réintégrations fiscales (plafonds VP, LOA), IS.
- [ ] **Liasse pivot** case-par-case alignée dictionnaire TDFC, formulaires sélectionnés par le statut du dossier : 2065 + 2050/2033 (IS) et 2031 + annexes (option IR) + contrôles de cohérence inter-cases. **Avancé le 2026-09-23 (doc 17 §15)** : 2065 + 2033-A à G complets pour l'IS au régime simplifié, cases indexées par le code officiel, sans relecture d'expert-comptable (décision démo). **2031 + 2031-bis faits le 2026-09-26** pour la colonne à l'IR (EURL, SARL de famille, option 239 bis AB), 2033 jointe, pas d'IS ni de 2065 ; la colonne `societe_ir` de la matrice passe opérationnelle, et l'écran Exercice propose la 2065 ou la 2031 et masque le dépôt au greffe selon la matrice. **EI au réel opérationnelle le 2026-09-26** : 2031 + 2033, apport et prélèvements au compte de l'exploitant (108, capital individuel en 2033-A ligne 120), ni associés (2031-bis cadre E) ni composition du capital (2033-F), pas de dépôt au greffe ; dossier de référence `tests/closing/test_reference_ei_reel.py`. **Réel normal et contrôles faits les 14-15/10 (AXE-438)** : contrôles inter-cases avant livraison, 2050/2051, 2052/2053 et totaux 2054, 2055, 2056, 2058-A, 2058-B repris des chiffres de la 2033, sans PDF ni lignes de détail. Restent (AXE-484) : lignes de détail du 2054, 2057, 2058-C, 2059, PDF CERFA du réel normal.
- [ ] Renderers : FEC final (CI « Test Compta Demat »), PDF liasse fidèle CERFA, balance/GL/journaux exports, CA3 pré-remplie (CA12 en lecture d'historique seulement, doc 02 §7bis). **Avancé le 2026-09-23** : FEC conforme au texte de l'A.47 A-1 (pas encore passé dans Test Compta Demat), PDF 2065 + 2033 sur les formulaires officiels 2026, grand livre et balance en PDF. **Le 2026-10-14** : CA3 calculée dans le pivot, validateur FEC A.47 A-1 (ce n'est pas Test Compta Demat). Le FEC reste un fichier texte (AXE-422). Cases à zéro laissées vides sauf dans le FEC (AXE-557).
- [ ] Dossier de dépôt comptes annuels (Guichet Unique INPI) — génération, dépôt manuel documenté.
- [ ] Dossiers de référence supplémentaires (EURL avec LOA, EURL option IR clôturée, dossier traversant la **fin d'option IR** : exercice N en IR → N+1 en IS) en golden tests — un par colonne opérationnelle de la matrice doc 06 §7.
- [ ] Circuit de validation/relecture interne (statuts, verrous, doc 02 §2.3 — l'humain valide, c'est journalisé).
- [ ] Intégration signature électronique : paquets de documents, lien OTP mobile-first, suivi, relances (doc 11 §3.3).
- [ ] Workflow complet démontré : exercice clôturé → liasse → envoyée → signée → archivée.
- [ ] Deuxième relecture expert-comptable (clôture + liasses).

**Critère de sortie Phase 3** : un exercice complet du dossier de référence clôturé
de bout en bout, liasse conforme, FEC accepté, signature réelle effectuée sur staging.

---

## Phase 4 — Pilote client et durcissement

- [ ] Onboarding du tenant pilote : collecte de la liste statut/régime/TVA par chauffeur, création en masse des ~200 dossiers (chacun paramétré individuellement), profils d'import, reprise d'historique réelle.
- [ ] Adaptation ML au pilote (sur-pondération, doc 07 §3.3) + règles tenant.
- [ ] A/B testing : seuils d'auto-validation, présentation des explications (cadrage initial).
- [ ] Charge : reprise 10 ans (~3 M lignes), clôtures groupées (doc 09 §7).
- [ ] Chaos : pannes LLM/Digifactory/worker → reprise propre prouvée.
- [ ] Test d'intrusion externe + corrections.
- [ ] Runbook incident + exercice sur table (doc 10 §6).
- [ ] Restauration de sauvegarde chronométrée.
- [ ] Questionnaire sécurité du client complété ; SSO si exigé.
- [ ] Période de marche en double : la compta pilote produite en parallèle de
      l'existant pendant 2-3 mois, écarts analysés → c'est LE test de vérité.

**Critère de sortie Phase 4** : 3 mois de marche en double sans écart inexpliqué,
KPIs V1 atteints (doc 01 §6), feu vert du client.

---

## Phase 5 — Trajectoire cible

- [ ] Dossier d'habilitation **Partenaire EDI** déposé (doc 02 §5) : pièces administratives, clé publique, RDV correspondant régional.
- [ ] Génération EDIFACT/TDFC depuis la liasse pivot + attestation de conformité EDIFICAS.
- [ ] Télétransmission test puis réelle (TDFC, EDI-TVA) ; en attendant : intégration partenaire EDI tiers si le volume le justifie.
- [ ] API INPI Guichet Unique pour le dépôt des comptes.
- [ ] Onboarding industrialisé d'un nouveau client : < 2 semaines données → modèle adapté (doc 07 §3.3).
- [ ] **Nouveaux packs statut** selon la demande : EI au réel, micro-entreprise (livre des recettes + jauges de seuils), BNC/2035… (matrice doc 06 §7 — données et templates, pas de refonte).
- [ ] **Nouveaux packs métier** au premier client hors VTC : taxonomie, règles, templates du secteur.
- [ ] **UI mode mono-entreprise** : habillage direct sur le dossier unique (doc 11 §1bis) — la couche dossier existe déjà, on retire la couche portefeuille.
- [ ] Ingestion Factur-X via Plateformes Agréées (réforme 2026-2027).
- [ ] Étude certification NF 203 ; SSO entreprise ; mode sombre ; selon demande.

---

## Backlog transverse permanent (jamais « fini »)

- Chaque bug prod cœur comptable → post-mortem + fixture de non-régression (doc 09 §9).
- Veille millésimes fiscaux (TDFC, taux, plafonds CO2) → mise à jour des tables versionnées + goldens.
- Veille jurisprudence ordonnance 1945 (doc 02).
- Revue mensuelle des motifs d'escalade LLM → nouvelles règles.
- Échantillonnage mensuel des prompts sortants (contrôle pseudonymisation).
- Renouvellement dépendances (PR auto hebdo/mensuelle).

## Règles de pilotage du projet

1. **Le chemin critique est la donnée, pas le code** : l'audit du dataset (0.2) et
   la marche en double (4) sont les deux moments de vérité du projet.
2. À chaque fin de phase : revue des KPIs, mise à jour des docs, go/no-go explicite.
3. Tout ce qui touche au réglementaire (FEC, liasse, TVA) est validé par un
   expert-comptable avant production — budget récurrent assumé.
4. Périmètre V1 défendu agressivement : tout ce qui n'est pas dans les docs 01-12
   passe par une décision écrite (ADR ou mise à jour de doc), pas par un « vite fait ».
