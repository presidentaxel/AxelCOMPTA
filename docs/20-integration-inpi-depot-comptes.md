# 20 — Dépôt des comptes annuels (Guichet Unique INPI)

> **État au 2026-11-05** (ajouté) : le dossier de dépôt est généré et la
> signature reste fictive. Le choix du périmètre de la signature qualifiée
> RGS est prévu en décembre (AXE-441, ADR-004). Le dépôt reste manuel.

> **Statut : spike fait, renderer démo construit, le 2026-09-11** (doc 17
> §9 Semaine 4, doc 17 §10 — risque « schéma du dossier greffe/INPI
> inconnu »). Contrairement à Digifactory (doc 16) avant le doc 16, le
> schéma **est** documenté publiquement par l'INPI — pas besoin d'attendre
> un contact fournisseur pour commencer à coder. Le vrai blocage trouvé
> n'est pas technique, voir §5. **Louis (même jour) : signature fictive
> pour la démo, comparatif de prestataires pour la vraie signature qualifiée
> en V1** — voir §5 (code) et §6 (comparatif).
> Dernière mise à jour : 2026-09-11.

## 1. Contexte et décision

Doc 02 §6 : « Depuis 2023, formalités via le Guichet Unique (INPI). […]
Phase 1 : génération du dossier complet prêt à déposer (PDF + données),
dépôt manuel par le client. Phase 2 : intégration API. » Ce spike vérifie
si cette hypothèse (API = phase 2 seulement) tient — **elle ne tient
qu'à moitié** : l'API de dépôt existe et est documentée dès aujourd'hui,
mais un vrai blocage réglementaire (§5) rend la génération du dossier
« prêt à déposer manuellement » toujours la bonne cible court terme,
pour une raison différente de celle supposée au départ (pas un manque
d'accès API, mais une signature électronique qualifiée qu'AxeLCompta ne
peut pas fournir seul).

**Sources** (téléchargées le 2026-09-11 depuis
[inpi.fr/ressources/formalites-dentreprises/acces-aux-api-guichet-unique](https://www.inpi.fr/ressources/formalites-dentreprises/acces-aux-api-guichet-unique),
accès libre, pas de compte requis pour lire la doc) :
- **Contrat d'interface** (juin 2026, PDF, 52 pages) — le document
  principal de ce spike, contrat des endpoints REST.
- **Dictionnaire de données** (juin 2026, xlsx) — détail champ par champ,
  **pas encore dépouillé** (le contrat suffit pour l'estimation, pas pour
  une implémentation complète).
- **Catégorisation des activités** / **Liste des formes juridiques** —
  référentiels annexes, pas regardés (pas nécessaires pour le dépôt de
  comptes en tant que tel).

Une doc technique séparée existe pour la **consultation** des comptes
annuels d'un tiers (`documentation technique API_comptes_annuels v5.pdf`,
API Entreprise/RNE) — **non pertinente ici** : c'est une API de lecture
(chercher les comptes déjà déposés d'une entreprise), pas de dépôt.
À ne pas confondre si un futur spike y retombe.

## 2. Accès

Authentification requise (compte sur `procedures.inpi.fr`), **pas testée
en réel dans ce spike** — contrairement à Digifactory (doc 16), aucun
identifiant n'a été demandé/reçu à ce jour, ce spike s'est fait entièrement
sur la doc publique. Base URL de référence dans le contrat :
`guichet-unique.inpi.fr` (`https://guichet-unique.inpi.fr/api/docs/mandataire`
pour la doc Swagger interactive, non consultée ici faute de compte).

## 3. Le service de dépôt des comptes annuels

```
POST /api/annual_accounts
```

Corps (extrait du contrat, §4.1) :

```json
{
  "content": {
    "personnePhysique": {"...": "identité du déclarant, si personne physique"},
    "personneMorale": {"...": "identité de la société déposante"},
    "declarant": {"...": "qui dépose, au nom de qui"},
    "comptesAnnuels": {
      "comptesConsolides": null,
      "dateCloture": null,
      "dateDebutExerciceComptable": null,
      "dateFinExerciceComptable": null,
      "dispenseDepotAnnexes": null,
      "depotSimplifie": null,
      "modeExpert": {},
      "compteBilan": { "pagination": {}, "confidentiel": null },
      "compteResultat": { "pagination": {}, "confidentiel": null }
    }
  },
  "typePersonne": "P"
}
```

**Lecture (non confirmée dans le dictionnaire de données, ⚠️ à vérifier
avant implémentation)** : `compteBilan`/`compteResultat` ne portent pas de
montants case par case (pas un CERFA 2065 ré-implémenté) — `pagination`
suggère qu'ils pointent vers des **pages d'un PDF joint en pièce jointe**
(le bilan et le compte de résultat sont des sections d'un même document
PDF déposé, comme le fait déjà `PdfLiasseSimplifieeRenderer`/
`PdfCerfa2065Renderer`, doc 18). `confidentiel` correspond probablement à
l'option légale de confidentialité du compte de résultat pour les petites
entreprises (C. com. art. L.232-25) — cohérent avec le modèle de données
déjà pensé pour la matrice statut/régime (doc 06 §7), mais **à confirmer
avec le dictionnaire de données**, pas supposé ici.

**Pièces jointes** (§3.3 du contrat, mécanisme générique réutilisé ici) :
base64 dans `documentBase64`, format PDF uniquement, **10 Mo max par
pièce**, avec métadonnées (`nomDocument`, `typeDocument`, `path` —
l'endroit du JSON où la pièce s'attache). Codes retour standards (201
créé, 400 erreur de saisie, 401/403 auth, 500 serveur).

Endpoints complémentaires, non détaillés ici (contrat §4.2-4.7) : lister
les dépôts (`GET /api/annual_accounts`, filtrable par statut —
`VALIDATION_PENDING`, `SIGNATURE_PENDING`, `PAYMENT_PENDING`,
`AMENDMENT_*`, `VALIDATED`, `REJECTED`), détail d'un dépôt, version
allégée, régularisation, suppression d'un dépôt non payé, transfert à un
autre utilisateur.

## 4. Signature — le vrai chemin critique

**Différent de tout ce que le projet a signé jusqu'ici (doc 17 §8 :
« signature mockée, vrai faux » pour le chauffeur).** Le dépôt de comptes
annuels au greffe est soumis à l'art. R.123-5 du code de commerce :
signature électronique **avancée**, reposant sur un **certificat
qualifié** au sens du règlement eIDAS (UE 910/2014). Ce n'est pas une case
à cocher côté produit, c'est une obligation légale du dépôt lui-même.

Circuit documenté (contrat §6.3) :
1. `POST /api/annual_accounts` (les données + le PDF bilan/compte de
   résultat en pièce jointe).
2. Le Guichet Unique **génère lui-même** un « document de synthèse »
   (PDF, `typeDocument: "PJ_99"`) — **ce n'est pas AxeLCompta qui produit
   ce PDF final**, seulement les données/pièces en amont.
3. Télécharger ce PJ_99 (`GET /api/attachments/{fileId}/file`).
4. Le signer **côté poste client**, avec un certificat RGS — logiciel de
   signature + certificat que le déclarant doit posséder.
5. Reposter le PDF signé, typé `PJ_115` (`POST
   /api/annual_accounts/{id}/attachments`).
6. Confirmer la signature (`POST /api/signatures`, corps
   `{"annualAccount": "/api/annual_accounts/{id}", "signedDocument":
   "/api/attachments/{id}"}`).

**Implication directe pour AxeLCompta** : appeler cette API jusqu'au bout
suppose que le dossier (ou AxeLCompta pour son compte, en tant que
mandataire) dispose d'un certificat qualifié RGS — exactement le sujet
**déjà ouvert par ADR-004** (« prestataire de signature électronique »,
Yousign pressenti, doc 12 §0.1 toujours en devis). ADR-004 parlait de
signature pour les liasses/bilans en général ; ce spike **confirme
concrètement** que c'est une signature *qualifiée* précise (RGS), pas
n'importe quelle signature électronique avancée — à vérifier que Yousign
(ou le prestataire retenu) propose bien ce niveau de certificat avant de
signer un devis pour ce cas d'usage spécifiquement.

## 4bis. Deux signatures, deux rôles distincts (précisé 2026-09-11)

> **Preuve légale, même jour** : `SignatureRepository` est devenu
> append-only (doc 19 §8bis) — une signature ne peut plus être écrasée par
> la suivante. Condition nécessaire pour que la signature « validation »
> ci-dessous vaille comme preuve, indépendamment du choix de prestataire
> pour la signature « légale ».
>
> **Verrou en base, 2026-09-24** : `UPDATE` et `DELETE` sur
> `documents_signes` lèvent une erreur (migration `d8b41c6e0a27`).
> L'enregistrement écrit aussi une ligne dans `journal_audit` (acteur,
> horodatage, référence). Le PDF signé n'est pas recopié dans ce journal.

Clarification de Louis, importante pour ne pas tout confondre dans
`workflow/signature.py` (doc 18) : le parcours de clôture (doc 19 §5.3)
comporte **deux signatures séparées**, pas une seule répétée.

| | Signature 1 — validation | Signature 2 — légale |
|---|---|---|
| Qui signe | L'indiv | L'indiv |
| Sur quoi | Les comptes produits par AxeLCompta, avant tout envoi | Le document de synthèse renvoyé par l'organisme (ex. PJ_99 INPI, §4) après dépôt |
| Rôle | **Nous protège** — c'est l'acte de « l'utilisateur professionnel valide » (doc 02 §2.3) | **Légalement exigée** par l'organisme (ex. R.123-5 pour l'INPI, §4) |
| Niveau eIDAS requis | Aucun a priori — une confirmation simple suffit, pas besoin de qualifié | Qualifié RGS (INPI) — variable selon l'organisme, à vérifier au cas par cas |
| Prestataire | Peut rester interne (pas besoin d'ADR-004) | ADR-004, comparatif §6 |

**Implication code** (pas fait ici, pour plus tard) : `SignatureProvider`
(`workflow/signature.py`) modélise déjà la bonne distinction avec son
champ `qualifie: bool` — mais le renderer `PdfDepotInpiRenderer` construit
aujourd'hui (doc 17 §9) ne fait qu'une seule étape de signature (démo).
Le vrai parcours en a deux, avec un envoi aux organismes entre les deux
(doc 19 §5.3 points 10-12) — à revoir quand ce parcours sera codé pour de
vrai, pas juste renommé.

## 5. Ce que ça change pour le plan (doc 17 §9 Semaine 4, doc 12)

**Le blocage n'est plus « schéma inconnu » (résolu, §3) mais « signature
qualifiée non disponible »** — même famille de problème que Digifactory
(dépendance externe, pas un bug de notre côté), mais pas contournable par
un simple retest : il faut un vrai certificat RGS, donc une vraie décision
fournisseur (ADR-004), avant de pouvoir appeler `POST /api/signatures`
pour de vrai.

**Ce qui reste possible et utile sans lever ce blocage** (phase 1 de doc
02 §6, confirmée réaliste) : générer le dossier complet — PDF bilan/compte
de résultat + le payload JSON `content.comptesAnnuels` prêt à poster —
pour un dépôt **manuel** par le client sur `procedures.inpi.fr`, sans
jamais appeler l'API nous-mêmes.

**Construit le même jour, décidé avec Louis** : signature **fictive** en
démo (jamais qualifiée RGS), mais un vrai parcours technique pensé pour
la prod, pas un système à refaire (« on fait la démo en pensant à la
prod »). Ajouté :
- `axelcompta/filings/inpi_depot.py` — `construire_payload_comptes_annuels`
  (la vraie forme `content.comptesAnnuels` du §3, prête à poster telle
  quelle le jour où l'appel API est câblé) et `PdfDepotInpiRenderer` (tient
  lieu du document de synthèse que le Guichet Unique génère normalement
  lui-même, doc 08 §5 : filigrane **« DOCUMENT FICTIF — NE PAS DÉPOSER »**
  sans ambiguïté).
- `axelcompta/workflow/signature.py` — `SignatureProvider`/`DocumentSigne`/
  `SignatureRepository`, l'abstraction que branchera le vrai prestataire
  choisi (§7) sans changer la forme des appels ailleurs dans le code (même
  principe que `DataProvider`, doc 13 §2). `signature_demo.py` :
  `SignatureDemoProvider`, tamponne le PDF (« SIGNÉ — DÉMO AXELCOMPTA,
  DOCUMENT FICTIF » en diagonale rouge + mention signataire/horodatage) —
  `qualifie=False` toujours, signal explicite qu'aucun document produit
  par ce provider ne doit être déposé pour de vrai.
- `demo_api.py` : `GET /dossiers/{id}/greffe-inpi.pdf` (non signé par
  défaut, signé après action) et `POST
  /dossiers/{id}/greffe-inpi/signature` (« zone de signature qui finit le
  document », pas juste un badge React — persisté en mémoire, `dernier`
  reflète la dernière signature). `DossierResume` gagne
  `greffe_inpi_signe`.
- Frontend : `GreffeInpiSection.tsx` sur la fiche dossier — lien de
  téléchargement + bouton « Signer (démo) » + badge signé/non signé.
- **Vérifié en vrai navigateur** (pas juste tests) : clic réel sur Karim,
  badge passe à « signé », PDF retéléchargé différent (filigrane rouge en
  diagonale + ligne signataire/horodatage visibles), état persiste sur un
  GET ultérieur. 18 tests ajoutés (`tests/filings/test_inpi_depot.py`,
  `tests/workflow/test_signature.py`, 7 nouveaux dans
  `tests/test_demo_api.py`), mypy/ruff/import-linter/pytest tous verts
  (232 tests backend), `next lint`/`build` verts.

**Estimation retenue a posteriori** : ~2-3h pour le renderer + l'abstraction
signature + le câblage API + front + tests — dans l'ordre de grandeur
de l'estimation initiale (~0,5-1 jour), plutôt en dessous grâce à la
réutilisation directe des patterns déjà établis (`DataProvider`,
`DecisionRepository`). L'intégration API complète (dépôt réel + signature
qualifiée) reste hors de portée tant qu'ADR-004 n'a pas de prestataire
retenu.

## 6. Comparatif prestataires signature qualifiée RGS (recherche 2026-09-11)

Demande de Louis : une liste de partenaires possibles pour la vraie
signature qualifiée en V1, avec sa préférence explicite — **rester le
plus possible dans notre app**, quitte à renvoyer le chauffeur/gérant vers
le prestataire seulement si c'est techniquement impossible autrement.
Recherche faite sur documentation publique des prestataires (pas de devis
demandé, pas de contact pris) — **à valider par un vrai devis avant toute
décision ADR-004**, ceci est un défrichage, pas une recommandation
contractuelle.

| Prestataire | Parcours QES intégrable dans notre app ? | Modèle | Notes |
|---|---|---|---|
| **Universign** | **Oui** — leur doc technique dit explicitement que la vérification de pièce d'identité (étape bloquante pour Yousign, ligne suivante) se déroule **dans l'iframe**, sans redirection obligatoire. | API + iframe, paiement à l'usage a priori (pricing non confirmé, à demander) | Le candidat le plus proche de la préférence de Louis d'après cette recherche — **premier à recontacter pour un devis**. |
| **Yousign** (rebrandé **Youtrust** en 2026 — `developers.yousign.com` redirige vers `developers.youtrust.com`, ADR-004 à mettre à jour sur ce nom) | **Non pour la QES** — leur doc développeur le dit noir sur blanc : *« Signature levels: SES and AES. QES cannot be embedded »*. Bon pour de l'AES embarqué (si un usage futur du produit s'en contente), mais pour ce cas précis (dépôt INPI, QES obligatoire) il faut renvoyer l'utilisateur vers leur propre parcours (vérification vidéo, 100% à distance et asynchrone). | API-first, très orienté SaaS, pricing public | Écarter pour ce cas d'usage précis (dépôt greffe/INPI) tant que la QES reste non-embarquable chez eux — reste un candidat valable pour d'autres besoins de signature (AES) du produit. |
| **CertEurope / infocert-sign** (groupe Tinexta InfoCert) | **Non** — a un produit dédié **« Certificat de signature électronique qualifiée pour INPI »**, mais le modèle est : chaque signataire (le dirigeant du dossier) obtient son propre certificat individuel (~30 € HT, appel vidéo ~10 min), puis signe via leur appli desktop/web séparée (`infocert-sign`), pas via une intégration dans notre app. | Certificat **par personne physique**, 30 € HT one-shot | Modèle historiquement « natif » pour ce cas d'usage (page produit dédiée INPI), mais le coût est par dirigeant — sur ~200 chauffeurs/dirigeants SASU-EURL, ça chiffre vite (voir point ouvert ci-dessous) et le parcours sort systématiquement de notre app. |
| **Certigreffe** (Infogreffe, également via CertEurope) | **Non**, et pire : clé **USB physique**, retrait obligatoire dans un greffe de tribunal de commerce. | Certificat par personne, 119 €HT/an ou 249 €HT/3 ans | Écarté d'office pour un produit mobile-first sur 200 chauffeurs — logistique physique incompatible avec l'onboarding à distance (doc 14). Mentionné pour mémoire, c'est l'option « historique ». |

**Point ouvert ci-dessus — tranché par Louis (2026-09-11) : NON.**
AxeLCompta ne signera **jamais** comme mandataire avec son propre
certificat, quel que soit le gain économique/UX. Raison donnée par
Louis : signer, c'est engager sa responsabilité sur le dépôt — exactement
ce que la décision structurante n°1 du projet interdit déjà (README « Les
7 décisions structurantes » / doc 02 §2.3 : *« l'utilisateur professionnel
valide tout, AxeL ne tient pas la comptabilité en son nom »*). Ouvrir une
exception sur la signature de dépôt légal serait la pire porte d'entrée
possible pour cette responsabilité — **sujet clos, ne pas rouvrir** (même
formule que doc 12 §0.1 sur l'associé). Conséquence directe : **chaque
dirigeant (dossier) doit disposer de son propre certificat qualifié et
signer lui-même**, sans exception ni raccourci — ~200 signataires
individuels, pas un seul mandataire.

**Recommandation de ce spike** (pas une décision) : demander un devis à
**Universign** en premier — c'est le seul candidat trouvé où le parcours
d'obtention/usage d'un certificat **individuel** (un par dirigeant) peut
rester dans notre app via leur iframe, ce qui reste vrai et même plus
pertinent maintenant que le modèle mandataire est écarté : chaque
chauffeur passera par sa propre vérification d'identité, autant que ce
soit sans quitter l'app. CertEurope/Certigreffe restent des candidats de
repli (produit natif INPI) mais imposent de sortir de l'app pour chacun
des ~200 signataires — moins bon sur ce critère, à garder en tête
seulement si Universign ne convient pas en pratique (devis, POC).

## 7. Pas fait dans ce spike

- Compte e-procédures INPI créé/testé en réel (aucun appel HTTP réel,
  contrairement à Digifactory — tout ce doc vient de la lecture du
  contrat public).
- Dictionnaire de données (xlsx) dépouillé champ par champ — nécessaire
  avant toute implémentation réelle du payload `comptesAnnuels`.
- `personnePhysique`/`personneMorale`/`declarant` : structure non détaillée
  ici (probablement proche de ce qui existe déjà pour la formalité de
  création d'entreprise, contrat §1-3, non lu en détail — hors scope de ce
  spike, centré sur §4 dépôt de comptes).
- Confirmation du sens exact de `confidentiel`/`dispenseDepotAnnexes`/
  `depotSimplifie`/`modeExpert` (valeurs possibles, conditions
  d'éligibilité) — champs vus dans l'exemple du contrat mais pas définis
  dedans.
