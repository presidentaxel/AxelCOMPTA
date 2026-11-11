# 05 — Pipeline de catégorisation hybride et détection d'anomalies

> **État au 2026-11-10** (ajouté ; le reste du doc décrit la cible) :
> - Ordre réel (AXE-826) : virements internes (deux jambes opposées sur
>   deux comptes du dossier), règles du pack, modèle, puis catégorie de la
>   banque (Bridge) en simple proposition, jamais imputée seule.
> - Étage 1 (règles) et étage 2 (modèle v2 calibré : proposition au-dessus
>   de 0,6, imputation automatique au-dessus de 0,95 pour 9 catégories
>   seulement) en place, plus les propositions apprises des décisions du
>   chauffeur. Une règle peut avoir un plancher de montant : en dessous,
>   elle propose sans imputer (carburant à 5 €, AXE-837). Retraits
>   d'espèces : question dédiée au chauffeur (AXE-844).
> - Sans modèle, la synchro s'arrête et le dit (AXE-825) ; repli sur les
>   règles seules avec `AXELCOMPTA_SANS_MODELE=1`. Le modèle n'est encore
>   que sur un poste (AXE-830, AXE-847).
> - Étage 3 (LLM) : la pseudonymisation et l'interface `LLMProvider` existent
>   (AXE-436), aucun fournisseur n'est branché.
> - Étage 4 (humain) : « À traiter » côté chauffeur, mode expert côté
>   expert-comptable habilité, motif obligatoire (AXE-800). Une décision
>   s'écrit au grand livre en OD de reclassement (AXE-420). Le mode expert
>   relit aussi les opérations déjà classées et note « juste » ou « faux »
>   (AXE-823).
> - Anomalies (§6) : profils et détecteurs V1 faits (AXE-437), détecteurs
>   carburant affinés (AXE-836) ; qualifications en base avec historique
>   (AXE-814).
> - Aucun objectif du doc 01 §6 n'est encore mesuré (AXE-816).

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-12

C'est le cœur « intelligent » du système, conçu exactement comme exprimé dans le
besoin initial : **rigide d'abord** (règles codées en dur, variance nulle), **ML
ensuite** (généralisation), **LLM en dernier** (arbitrage des cas ambigus), **humain
toujours en bout de chaîne** pour ce qui compte.

## 1. Architecture en étages

```mermaid
flowchart TD
    T[NormalizedTransaction] --> R{Étage 1<br/>Règles dures}
    R -- "match exact<br/>confiance = 1.0" --> OUT[CategorizationProposal]
    R -- pas de match --> ML{Étage 2<br/>Modèle ML}
    ML -- "confiance ≥ τ_ml" --> OUT
    ML -- "confiance < τ_ml" --> LLM{Étage 3<br/>LLM arbitre}
    LLM -- "accord ML+LLM<br/>ou confiance haute" --> OUT
    LLM -- désaccord / incertitude --> H[Étage 4<br/>File de revue humaine]
    H --> OUT
    OUT --> AB{Auto-validation ?}
    AB -- "règle dure + tenant l'autorise<br/>+ aucune alerte anomalie" --> AUTO[Écriture auto-validée]
    AB -- sinon --> VAL[Validation humaine]
```

Objectifs chiffrés par étage (cf. KPIs doc 01) : règles ≥ 60 % des transactions,
ML ~30 %, LLM ≤ 10 %, revue humaine ce qui reste. Le coût et la variance augmentent
à chaque étage ; le volume doit diminuer.

## 2. Étage 1 — Règles dures (déterministe, biais maîtrisé)

### 2.1 Nature des règles

Des règles **déclaratives, versionnées en base, testables**, à trois niveaux de
priorité :

1. **Règles système** : enseignes nationales sans ambiguïté, livrées par **pack
   métier** (doc 03 §3bis) — le pack VTC fournit p. ex. `libellé contient
   "TOTALENERGIES|ESSO|BP STATION" → 6061 carburant (TVA récup. partielle selon
   véhicule)` ; un futur pack restauration ou BTP aura les siennes.
2. **Règles tenant** : spécificités du client. Ex. sa commission de gestion,
   le loyer LOA prélevé par tel organisme → `6122 redevances crédit-bail`.
3. **Règles dossier** : apprises des corrections. Quand un humain corrige 3 fois le
   même couple (créancier, catégorie) sur un dossier, le système **propose** de
   créer une règle (jamais silencieusement).

### 2.2 Anatomie d'une règle

```yaml
id: rule-fuel-total-001
priorite: 100
porte: systeme
conditions:
  libelle_regex: '(?i)\b(TOTAL\s?ENERGIES|RELAIS\s)\b'
  montant: { min: -30000, max: -200 }       # centimes : 2 € à 300 € débit
  sens: debit
action:
  categorie: carburant
  compte_pcg: "60611"
  tva: { taux: 20, recuperation: "selon_vehicule" }  # résolue par le paramétrage dossier
  confiance: 1.0
tests:                                       # chaque règle embarque ses cas de test
  doit_matcher: ["CB TOTALENERGIES PARIS 15", "RELAIS TOTAL A6"]
  ne_doit_pas_matcher: ["TOTAL LOOK COIFFURE"]   # 😉 les pièges réels
```

**Toute règle a des cas de test embarqués, exécutés en CI.** Une règle sans test ne
peut pas être activée. Les collisions entre règles (deux règles matchent) sont
résolues par priorité et **journalisées** pour révision.

### 2.3 Pourquoi cet étage est premier

Variance nulle, explicabilité parfaite (« la règle X a matché »), coût zéro,
auditabilité totale — exactement ce qu'un contrôleur ou une banque veut entendre.
Tout investissement qui déplace du volume du ML vers les règles est rentable.

## 3. Étage 2 — Modèle ML

Détails d'entraînement dans doc 07. Ici, le contrat d'intégration :

- **Entrée** : features dérivées de `NormalizedTransaction` (texte du libellé
  nettoyé, montant, jour de semaine, récurrence détectée, MCC si fourni par Bridge,
  catégorie Bridge si fournie — *feature*, pas vérité).
- **Sortie** : distribution de probabilités sur la **taxonomie du pack métier du
  dossier** (le pack VTC : ~40-80 classes — carburant, péage, lavage, entretien,
  assurance, LOA, commissions plateformes, téléphone, repas, parking…), chaque
  catégorie étant mappée vers un compte PCG par le paramétrage du dossier (le
  compte final peut différer selon le statut/régime du dossier).
- **Seuil τ_ml par classe, pas global** : on exige plus de confiance pour les
  classes à enjeu (immobilisations, rémunérations) que pour un péage.
- **Calibration obligatoire** (Platt/isotonic) : un score de 0,9 doit vouloir dire
  90 % de chances d'avoir raison, sinon les seuils ne signifient rien.
- Le modèle est un **artefact versionné** (registry, doc 07 §6) chargé au démarrage.
  Pas d'entraînement dans le runtime API, jamais.

> **Ce qui est codé au 2026-09-27** (`backend/axelcompta/categorize/`, détail
> dans son README) :
> - **Signe** : le montant bancaire est retourné en convention FEC avant le
>   modèle, qui a appris sur des FEC (charge positive).
> - **Garde de sens** : une charge n'est jamais proposée pour un
>   encaissement, un produit jamais pour un décaissement, pour les règles
>   comme pour le modèle.
> - **Calibration et seuils par catégorie (2026-09-27)** : régression
>   isotone sur les prédictions hors échantillon, erreur de calibration
>   (ECE) de 0,097 à 0,019 ; la confiance affichée est une chance réelle
>   d'avoir raison. Proposition au-dessus de 0,6 calibré (75,7 % des lignes,
>   90,0 % justes). Imputation automatique au-dessus de 0,95 calibré, pour
>   les seules catégories qui y atteignent 95 % de justesse sur au moins 30
>   lignes, jamais les catégories à enjeu ni à risque d'usage personnel
>   (fournitures, repas) : 29,8 % des lignes, 98,5 % justes. Mesures en
>   validation croisée imbriquée par dossier. Sans fichier de calibration,
>   les seuils bruts historiques (0,5 et 0,90) s'appliquent.
> - **Propositions apprises** : une opération semblable à une opération déjà
>   tranchée par l'indiv, dans le même sens, reprend sa catégorie
>   (`appris.py`). Proposée seulement, jamais imputée.

## 4. Étage 3 — LLM arbitre

- **Quand** : confiance ML < τ_ml, ou catégorie à enjeu, ou libellé jamais vu.
- **Quoi** : prompt structuré contenant le libellé **pseudonymisé** (doc 10 §4), le
  montant, le contexte métier issu du pack du dossier (« chauffeur VTC », demain
  « boulangerie »…), le top-3 du ML avec ses scores, la taxonomie autorisée, et les
  données du justificatif matché s'il existe.
- **Sortie contrainte** : JSON schema strict — `{categorie ∈ taxonomie, confiance,
  justification_courte}`. Toute sortie hors schéma = rejet → revue humaine. Le LLM
  ne peut **pas** inventer de catégorie.
- **Politique de décision** :
  - LLM et ML d'accord → proposition avec confiance renforcée.
  - Désaccord → revue humaine, avec les deux avis affichés.
  - Le LLM seul ne suffit jamais à auto-valider.
- **Abstraction multi-fournisseurs** (`LLMProvider`) : Claude / Gemini / OpenAI
  interchangeables, fallback en cas de panne, budget par tenant, cache des réponses
  par libellé-type (un même libellé récurrent ne paie qu'un appel).
- **Boucle d'amélioration** : chaque cas envoyé au LLM est un signal que règles et
  ML ont une lacune. Revue mensuelle des motifs d'escalade → nouvelles règles ou
  réentraînement.

## 5. Étage 4 — Revue humaine

- **« Humaine » = l'utilisateur professionnel côté client (gestionnaire, son
  service compta, son expert-comptable), jamais quelqu'un chez AxeL.** Ce
  n'est pas une nuance UX, c'est la conséquence directe du positionnement
  légal (doc 02 §2.3) : AxeL n'impute pas, ne surveille pas, ne tranche pas
  *en son nom* — sinon on retombe dans le monopole de l'expertise comptable.
  Si un item de la file de revue est qualifié par une source déléguée par le
  gestionnaire (ex. le chauffeur lui-même, pour dire ce qu'était une dépense
  ambiguë), le mécanisme reste à spécifier — canal d'escalade envisagé mais
  pas encore couvert par ce document (2026-09-02).
- File de travail priorisée : alertes d'abus > catégories à enjeu > gros montants >
  reste. Temps de décision visé < 10 s par item (UI, doc 11).
- **Chaque correction humaine est de l'or** : stockée comme label
  (`PROPOSITION.source = HUMAN`), elle alimente le réentraînement et le minage de
  règles. C'est la boucle de fine-tuning par client demandée.
- **La décision humaine est immuable une fois posée dans le ledger — personne
  chez AxeL ne la modifie a posteriori** (conséquence directe du
  positionnement légal, doc 02 §2.3 : ce serait rendre la décision à sa
  place). Le fine-tuning se fait sur un objet séparé, une **annotation dev**
  (juste/faux + note libre) posée sur la décision existante, jamais en
  écrivant par-dessus. Un dev qui repasse sur une correction humaine peut la
  juger discutable pour l'entraînement du modèle sans jamais y toucher dans
  le ledger — deux pistes d'audit distinctes : « ce que le client a décidé »
  (source de vérité comptable/légale) et « ce que AxeL en pense pour
  l'algo » (signal ML interne, jamais exposé côté client comme une
  correction). Précisé le 2026-09-07, suite à une discussion sur la démo
  (doc 17) mais s'applique à l'architecture cible, pas qu'à la démo.
  Depuis le 2026-09-24, ce n'est plus seulement une convention du dépôt :
  `UPDATE` et `DELETE` sont refusés en base sur `decisions_humaines`
  (migration `d8b41c6e0a27`, même fonction que les écritures). Corriger
  une décision, c'est en enregistrer une nouvelle. L'insertion est tracée
  dans `journal_audit` (`workflow/audit.py`), dans la même transaction.

## 6. Détection d'anomalies et d'abus (module `anomaly`)

### 6.1 Posture

Le module **signale des incohérences**, l'humain qualifie. Aucune sortie du système
n'emploie de qualification juridique (« abus de biens sociaux ») ; vocabulaire UI :
« dépense à justifier », « dépense atypique », « usage personnel possible ».

### 6.2 Le profil comportemental individuel (la clé du « chaque dossier a son analyse »)

Chaque dossier porte un **profil comportemental** appris automatiquement de son
propre historique : consommation habituelle par catégorie (moyenne, dispersion,
saisonnalité), enseignes récurrentes, montants types, fréquences. C'est une fiche
de statistiques recalculée incrémentalement — pas un modèle entraîné par dossier —
donc ça passe à l'échelle sur 200 ou 2 000 dossiers sans coût notable (doc 07 §3.3).

C'est ce profil qui permet de capter « ce chauffeur a consommé plus que d'habitude
cette fois-ci » : la détection compare chaque transaction aux habitudes de **ce**
dossier, pas à une moyenne globale. Les seuils et catégories surveillées viennent
du pack métier (le pack VTC surveille carburant/entretien ; un autre pack
surveillera d'autres postes).

### 6.2bis Détecteurs (du plus simple au plus riche)

| Détecteur | Type | Exemple capté |
|-----------|------|---------------|
| Catégorie intrinsèquement personnelle | Règle (pack) | Vétérinaire, jouets, abonnement streaming personnel sur le compte pro. |
| Enseigne ambiguë + montant/ticket incohérent | Règle + OCR | Auchan 87 € sans ticket carburant, ou ticket listant des courses alimentaires. |
| Écart au profil comportemental du dossier | Stats (§6.2) | Dépense carburant 3σ au-dessus de l'habitude de CE chauffeur ; plein d'essence 2× le même jour. |
| Cohérence métier (règles du pack) | Règle métier | Pack VTC : carburant sans activité de courses sur la période ; péages un jour sans recettes. |
| Doublons de remboursement | Règle | Même justificatif matché sur deux transactions. |
| Comparaison aux pairs du portefeuille | ML (phase 2) | Ratio entretien/CA très au-dessus des dossiers comparables du même pack. |
| Week-end/horaires (prudent) | Stats (phase 2) | Signal faible seulement — pondéré par le profil du dossier (les VTC travaillent le week-end), jamais utilisé seul. |

### 6.3 Cycle de vie d'une alerte

`ouverte → en instruction → justifiée (avec pièce/commentaire) | confirmée usage
personnel → traitement comptable (455 ou 108 selon le statut configuré du dossier,
doc 06 §7) | faux positif (→ label d'entraînement)`.

Tout est journalisé : qui a instruit, décision, pièces. C'est la valeur ajoutée
pour le client gestionnaire (conformité) et une donnée d'entraînement pour
améliorer la précision des détecteurs.

### 6.4 Mesure

Le rappel (ne pas rater de vrais abus) prime sur la précision à volume d'alertes
soutenable : cible V1 = rappel ≥ 80 % avec ≤ 5 % des transactions alertées.
Jeu d'évaluation : abus historiques connus du client + abus synthétiques injectés.

## 7. Explicabilité de bout en bout

Pour chaque écriture finale, on doit pouvoir afficher (et exporter pour un audit) :

> Transaction `CB AUCHAN CARBURANT 12/03` −67,40 € → catégorie **carburant** par
> **règle systeme rule-fuel-auchan-002 (v3)**, ticket matché #4521 (confiance 0,97),
> TVA récupérée 80 % (véhicule de tourisme, paramétrage dossier), validée par
> M. Dupont le 14/03/2026, écriture n° 2026-AC-00871.

Cette traçabilité est un invariant produit : aucune étape du pipeline ne peut
produire une proposition sans renseigner sa source, sa version et ses entrées.
