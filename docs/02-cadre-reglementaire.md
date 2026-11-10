# 02 — Cadre réglementaire et juridique

> Statut : brouillon à valider — Dernière mise à jour : 2026-11-05 (mode expert, §2.3)

## 1. Pourquoi ce document existe

AxeLCompta touche à quatre domaines réglementés simultanément :

1. La **profession comptable** (ordonnance n° 45-2138 du 19 septembre 1945).
2. Les **données bancaires** (DSP2, secret bancaire, RGPD).
3. Les **obligations comptables et fiscales** (PCG, FEC, liasses, dépôts).
4. La **télétransmission fiscale** (habilitation Partenaire EDI).

Chacun peut être un *no-go* s'il est ignoré. Aucun n'en est un si on le traite.

## 2. Monopole de l'expertise comptable : où est la ligne

### 2.1 Le texte

L'ordonnance n° 45-2138 du 19/09/1945 (art. 2 et 20) réserve aux experts-comptables
inscrits à l'Ordre le fait de « tenir, centraliser, ouvrir, arrêter, surveiller,
redresser et consolider les comptabilités » **pour le compte de tiers**, de façon
habituelle et en son nom propre. L'exercice illégal est un délit pénal.

### 2.2 La jurisprudence qui nous concerne

**Cass. com., 17 septembre 2025, n° 24-14.689** (publié au bulletin) :

> « La saisie informatique de données comptables dans un logiciel dédié ne relève
> pas, à elle seule, du champ de compétence réservé aux experts-comptables. »

Lecture correcte de l'arrêt — et c'est important de ne pas le sur-interpréter :

- ✅ La **saisie / le traitement informatique** de données comptables n'est pas, en
  soi, un acte réservé. Un logiciel qui impute automatiquement des écritures que
  l'utilisateur contrôle est licite.
- ⚠️ L'arrêt ne dit **pas** que tenir la comptabilité de tiers est devenu libre. Les
  juges doivent regarder *l'ensemble de la prestation* : l'**habitude**, la
  **responsabilité assumée en nom propre**, les travaux intellectuels
  d'**imputation, d'analyse, de surveillance**. Si on coche ces cases, on retombe
  dans le monopole.
- ⚠️ La chambre criminelle continue de condamner (ex. Cass. crim. 21/01/2026,
  n° 24-81.008, sur la mise à disposition habituelle de personnel comptable).

### 2.3 Notre positionnement (à graver dans le produit ET les contrats)

**AxeL est un éditeur de logiciel, pas un prestataire de tenue comptable.**

Conséquences concrètes, à implémenter dans le produit :

> **Précisé le 2026-09-11 (doc 19) : l'« utilisateur professionnel » qui
> valide, c'est l'indiv (le dirigeant du dossier), pas le gestionnaire
> portefeuille.** Le gestionnaire n'a jamais accès aux transactions/
> justificatifs/documents d'un dossier — c'est l'indiv qui dépense, qui
> sait, qui valide. Le gestionnaire signe un contrat avec nous, pas avec
> chaque dossier ; il gère l'onboarding (invitations) et voit un état des
> lieux agrégé (doc 19 §6), jamais le détail. Ce n'est pas un simple choix
> UX — ça renforce directement cette ligne : faire valider par le bon
> « utilisateur professionnel » (celui qui a l'information réelle), pas un
> tiers qui ne peut que faire confiance aux chiffres qu'on lui montre.

| Règle produit | Implémentation |
|---------------|----------------|
| L'utilisateur professionnel — **l'indiv, propriétaire du dossier**, pas le gestionnaire portefeuille — **valide** chaque période avant production des états | Étape de validation obligatoire et non contournable dans le workflow (côté indiv, doc 19) ; journalisée. **Deux signatures distinctes** (doc 20 §4bis) : une validation qui nous protège (l'indiv atteste que les comptes sont exacts), une signature qualifiée RGS sur les documents effectivement déposés — pas la même chose, pas le même prestataire nécessairement. |
| La responsabilité de la comptabilité reste celle du client | CGV/CGU explicites ; mention sur chaque document généré (« Document préparé via AxeLCompta, validé par [utilisateur] le [date] »). |
| Les propositions automatiques sont des **propositions** | UI : statut « proposé » vs « validé » ; les écritures non validées ne sortent jamais dans un état définitif. |
| AxeL n'analyse pas, ne surveille pas, ne redresse pas *en son nom* | Les alertes (anomalies, abus potentiels) sont adressées à l'utilisateur, qui décide. Pas de rapport signé AxeL. |
| Pas de prestation humaine de saisie chez AxeL | Si un jour on propose du service, le faire via un cabinet EC partenaire. |
| **Le logiciel ne décide jamais d'une imputation** : c'est le chauffeur, ou l'expert-comptable de l'entreprise dans le mode expert | Rôle `expert_comptable` distinct, activé seulement après un engagement de responsabilité accepté et tracé ; chaque changement porte son auteur et son motif (AXE-800, voir ci-dessous). |

> **Mode expert — décision de Louis du 2026-11-05.** Le mode expert (file de
> tout ce qui est à traiter, « Imputer ») vise une entreprise qui gère sa
> flotte **avec un expert-comptable**. C'est l'expert-comptable qui décide
> de chaque imputation, dans le cadre de sa lettre de mission ; AxeL ne fait
> que l'outil, il ne propose rien qui s'écrive seul. Pour que ce soit
> prouvable, celui qui change une écriture en **prend la charge juridique** :
> - rôle `expert_comptable` séparé d'admin, membre et lecture, avec nom,
>   cabinet, numéro d'inscription à l'Ordre et lettre de mission (dossiers
>   couverts) ;
> - engagement de responsabilité (texte versionné, relu par un juriste,
>   AXE-813) accepté avant tout accès, gardé mot pour mot dans le journal
>   d'audit ;
> - chaque imputation, annulation ou qualification d'anomalie enregistre son
>   auteur, son motif et la version de l'engagement ; le chauffeur voit qui a
>   reclassé son opération et pourquoi ;
> - sans ce rôle et cet engagement, l'API refuse l'écriture (403).
>
> **Livré le 2026-11-09 (AXE-800).** Un admin habilite l'expert dans Équipe
> (`habilitations_expert`) ; l'expert accepte l'engagement à sa première
> visite du mode expert (`engagements_expert`, texte, date et adresse) ;
> chaque imputation, annulation ou qualification s'écrit dans
> `decisions_expert` avec ses écritures, dans la même transaction. Les trois
> tables sont en ajout seul. Le mode expert, les anomalies, les opérations
> classées et la quarantaine répondent 403 à tout autre rôle. **Le texte de
> l'engagement (`workflow/expert_comptable.py`) reste à faire relire par un
> juriste (AXE-813)** : toute modification change sa version, et chaque
> expert l'accepte de nouveau.

### 2.4 Piste complémentaire

Un **partenariat avec un cabinet d'expertise comptable** reste une option commerciale
(rassure les banques, débloque la mission de présentation pour les dossiers qui en
veulent une). À garder pour la phase 2, ce n'est pas bloquant pour la V1.

## 3. Données bancaires : DSP2, Bridge, secret bancaire

- **Bridge** (bridgeapi.io) est un prestataire agréé ACPR (agrégation de comptes /
  AISP au sens de la DSP2). En passant par Bridge, AxeL n'a **pas besoin d'agrément
  AISP propre** : Bridge porte l'agrément, nous consommons son API. À vérifier au
  contrat : nous sommes « agent » ou simple client technique.
- **Pour le pilote (septembre 2026), l'accès ne passe pas par un contrat Bridge
  direct** : Digifactory, déjà client Bridge, agrège les données par contact et
  nous expose sa propre API (doc 16). Nous ne sommes donc pas partie au contrat
  Bridge sur cette période. Un accès Bridge direct (application séparée,
  sandbox) est une piste parallèle non bloquante testée plus tard (doc 16 §8).
  Ceci ajoute une **chaîne de sous-traitance à trois** (chauffeur → Bridge →
  Digifactory → nous) dont la couverture RGPD par le consentement DSP2 n'est
  pas confirmée — point ouvert, doc 10 §3, doc 16 §6.
- Le **consentement** du titulaire du compte (le gérant du dossier ou sa société) est requis
  et renouvelable (180 jours sous DSP2). Le parcours de consentement est géré par
  Bridge Connect, mais nous devons tracer qui a consenti, quand, pour quels comptes.
- **Secret bancaire / exigences sectorielles** : un client du secteur financier imposera son propre cadre (contrat de
  sous-traitance, audits sécurité). Prévoir un questionnaire sécurité exigeant
  (voir doc 10).

## 4. Obligations comptables à respecter dans le moteur

| Obligation | Source | Impact produit |
|------------|--------|----------------|
| Plan Comptable Général (PCG 2025, règlement ANC n° 2022-06) | ANC | Référentiel de comptes embarqué, versionné. |
| Partie double, balance toujours équilibrée | PCG | Invariant logiciel absolu (voir doc 06). |
| Caractère **définitif** des écritures validées (intangibilité) | PCG art. 921-2 ; LPF | Pas de modification d'une écriture validée : contre-passation uniquement. Journalisation immuable. Trigger et contre-passation d'une transaction bancaire déjà comptabilisée : en code le 2026-09-24 (doc 06 I2). |
| Numérotation séquentielle, datation, pièce justificative référencée | PCG | Chaque écriture porte une référence de pièce (ou un statut « pièce manquante »). |
| **FEC** (fichier des écritures comptables) conforme art. A.47 A-1 LPF | DGFiP | Export FEC testé contre l'outil officiel « Test Compta Demat » en CI. |
| Conservation 10 ans des pièces | Code de commerce L.123-22 | Archivage WORM (write once read many) des justificatifs et écritures. |
| Dépôt des comptes annuels (sociétés) | C. com. | Génération du dossier de dépôt via le Guichet Unique (INPI). |

Note : la certification **NF 203** (logiciels comptables) n'est pas obligatoire mais
crédibilise fortement face à une banque. À étudier en phase 2. La NF 525 (caisse) ne
nous concerne pas tant qu'on n'encaisse pas.

## 5. Télédéclaration : stratégie en trois temps

Seul un **Partenaire EDI habilité DGFiP** peut transmettre TDFC, EDI-TVA,
EDI-PAIEMENT. Notre trajectoire :

### Temps 1 — Lancement : pas de télétransmission directe
- Génération des liasses et déclarations en **PDF + export structuré**.
- Saisie manuelle sur impots.gouv.fr (mode EFI) par le client, ou dépôt via son
  expert-comptable.
- **Décision d'architecture clé** : le moteur produit dès le départ une
  **représentation interne pivot de la liasse** (formulaires + codes des cases,
  alignés sur le dictionnaire TDFC officiel), dont PDF et EDI ne sont que des
  *renderers*. Ainsi le passage au temps 2 et 3 ne change pas le cœur.

### Temps 2 — Croissance : partenaire EDI tiers
- Contrat avec un partenaire EDI existant (jedeclare.com, ASPOne, etc.) qui
  transmet pour notre compte / celui de nos clients (mandat).
- Nous générons les interchanges au format attendu — d'où l'importance du pivot.

### Temps 3 — Cible : habilitation Partenaire EDI propre
Procédure (source : impots.gouv.fr, BOI-BIC-DECLA-30-60-30-20) :

1. **Phase administrative** : dossier à la Direction des finances publiques du
   chef-lieu de région — demande d'habilitation, fiche d'information, présentation
   de l'activité, attestation de régularité fiscale, convention DGFiP-Partenaire EDI
   signée. Délivrance d'un **numéro d'agrément**.
2. **Phase technique** : accréditation par clé publique (fichier de clé envoyé au
   correspondant régional téléprocédures, rendez-vous de remise), puis connexion à
   l'ESI de Strasbourg.
3. **Conformité des messages** : les interchanges EDIFACT doivent être produits par
   un logiciel ayant l'**attestation de conformité délivrée par EDIFICAS**. C'est un
   chantier à part entière (cahiers des charges TDFC volumineux, mis à jour chaque
   année — millésime 2026 publié).

Pré-requis internes avant de candidater : SAS à jour fiscalement, infrastructure
stable, moteur de liasse éprouvé en production via les temps 1 et 2.

## 6. Dépôt des comptes annuels (INPI / greffe)

- Depuis 2023, formalités via le **Guichet Unique** (INPI). Les comptes annuels des
  sociétés (les SASU/EURL de chaque dossier géré) y sont déposés.
- L'INPI propose des dépôts dématérialisés ; une **API formalités** existe, schéma
  documenté publiquement (`POST /api/annual_accounts`, spike 2026-09-11, voir
  [doc 20](20-integration-inpi-depot-comptes.md)). Phase 1 : génération du dossier
  complet prêt à déposer (PDF + données), dépôt manuel par le client. Phase 2 :
  intégration API — **révisé** : ce n'est plus un simple manque de doc qui la
  bloque (le schéma est connu), mais l'obligation légale de **signature
  électronique qualifiée RGS** (C. com. art. R.123-5) pour le dépôt réel, qui
  recoupe ADR-004 (prestataire de signature non encore retenu, doc 12 §0.1).
- L'entité déposante et la nature du dépôt dépendent du **statut configuré par
  dossier** (doc 06 §7) : société IS/IR → dépôt INPI ; EI → pas de dépôt de comptes ;
  futur cas CAE → la coopérative dépose pour elle-même. Le moteur lit cette
  configuration, jamais de cas particulier codé en dur.

## 7. Facturation électronique (réforme 2026-2027)

Calendrier en vigueur : **1er septembre 2026** — obligation de *réception* pour
toutes les entreprises, émission pour les grandes et ETI ; **1er septembre 2027** —
émission pour PME/TPE. Conséquences pour nous :

- Les factures arriveront de plus en plus en **Factur-X / UBL / CII** via des
  Plateformes Agréées (PA). C'est une **opportunité** : données structurées fiables
  en entrée, moins d'OCR.
- L'ingestion justificatifs (doc 04) doit traiter Factur-X en *first-class citizen*,
  l'OCR devenant le fallback pour tickets et documents non structurés.
- Devenir PA nous-mêmes : **non-objectif** (coût d'immatriculation disproportionné).
  S'intégrer aux PA du marché suffit.

## 7bis. Suppression du régime réel simplifié de TVA (réforme au 1er janvier 2027)

- **Calendrier** : à compter du 1er janvier 2027, le **régime réel simplifié de
  TVA (RSI) est supprimé**. Les entreprises concernées basculent automatiquement
  vers le **régime réel normal** — aucune démarche requise de leur part.
- **Contexte** : avec la généralisation de la facturation électronique et de
  l'e-reporting (§7 ci-dessus), un système fondé sur des acomptes forfaitaires
  n'a plus de sens pour l'administration, qui veut collecter la TVA au fil de
  l'eau.
- **Conséquence déclarative** : fin des deux acomptes semestriels et de la
  régularisation annuelle CA12 ; passage à une **déclaration mensuelle (CA3)**
  par défaut, ou trimestrielle sur option. Le régime simplifié agricole n'est
  pas concerné par cette suppression.
- **Conséquence produit — décision** : le calendrier de cette réforme tombe en
  plein milieu de notre Phase 1 (doc 12, 2026-08 → 2027-02) — le régime
  simplifié sera obsolète **avant même le pilote client** (Phase 4, 2027-05).
  On ne construit donc pas le réel simplifié/CA12 comme cible V1 : le **réel
  normal (CA3 mensuelle) devient la seule trajectoire TVA construite pour de
  nouveaux dossiers**. Le réel simplifié reste supporté uniquement en **lecture
  de l'historique** (dossiers repris avec des exercices antérieurs à 2027) —
  jamais comme régime dans lequel on fait entrer un dossier après le
  basculement. Voir doc 06 §6-7 pour la traduction dans le moteur.

## 8. RGPD appliqué au projet

Voir doc 10 pour le volet technique. Points juridiques :

- **Base légale** : exécution contractuelle (traitement comptable) + intérêt légitime
  (détection d'anomalies). La détection d'« abus » est un traitement sensible en
  pratique : il **profile des personnes** — documenter une AIPD (analyse d'impact).
- **Entraînement ML sur 10 ans d'historique** : vérifier que le contrat avec le
  client couvre la réutilisation des données à des fins d'entraînement ;
  pseudonymiser le dataset d'entraînement ; minimisation (on n'a pas besoin des noms
  pour catégoriser un libellé bancaire).
- **LLM externes** : aucune donnée nominative ne sort. Pseudonymisation systématique
  (noms, IBAN, numéros) avant tout appel Claude/Gemini/OpenAI + endpoints UE quand
  disponibles + opt-out de l'entraînement fournisseur. Registre des traitements à
  jour.
- **Droits des personnes** : les gérants des dossiers (chauffeurs…) ne voient pas la plateforme mais restent
  des personnes concernées → procédure d'accès/rectification via le client
  (responsable de traitement ; AxeL = sous-traitant art. 28, DPA contractuel).

## 9. Synthèse des risques juridiques et parades

| Risque | Gravité | Parade |
|--------|---------|--------|
| Requalification en exercice illégal de l'expertise comptable | Existentielle | Validation humaine obligatoire, CGU « éditeur », pas de prestation humaine, veille jurisprudentielle. |
| Non-conformité FEC lors d'un contrôle fiscal d'un client | Élevée | Tests FEC automatisés en CI, outil DGFiP. |
| Fuite de données bancaires | Élevée | Doc 10 ; chiffrement, pseudonymisation LLM, audits. |
| Consentements DSP2 expirés → trous de données | Moyenne | Monitoring des consentements, relances automatiques via le client. |
| Refus d'habilitation Partenaire EDI | Faible (procédure ouverte) | Dossier préparé tôt, conformité EDIFICAS anticipée par l'architecture pivot. |

## 10. Actions juridiques avant production

- [x] Positionnement éditeur §2.3 — validé.
- [ ] Rédiger CGU/CGV + DPA (sous-traitance RGPD art. 28).
- [ ] AIPD pour le module de détection d'anomalies.
- [ ] Contrat Bridge : clarifier le statut (client technique vs agent) et les volumes — pertinent pour la piste directe (doc 16 §8), pas pour le canal Digifactory du pilote.
- [ ] Chaîne de sous-traitance RGPD à 3 (chauffeur → Bridge → Digifactory → nous) : le consentement DSP2 couvre-t-il la retransmission à Digifactory ? (doc 10 §3, doc 16 §6)
- [ ] Vérifier le droit d'usage des 10 ans de données historiques pour l'entraînement.
- [ ] Registre des traitements + désignation DPO (externe possible).
- [ ] **Nouveau (2026-09-11, doc 19 §3.4)** : le gestionnaire portefeuille
      peut-il légalement voir « documents déposés : oui/non » par dossier
      (sans le détail) ? C'est une donnée dérivée de la comptabilité d'un
      tiers (l'indiv), pas juste un statut technique — Louis n'est pas sûr
      que ce soit conforme RGPD/monopole (doc 02 §2). **Par défaut :
      désactivé** (le gestionnaire ne voit rien de dossier-spécifique au-delà
      des agrégats déjà prévus), à activer explicitement seulement après
      confirmation juridique. Ne pas coder l'option activée par défaut en
      attendant cette réponse.
