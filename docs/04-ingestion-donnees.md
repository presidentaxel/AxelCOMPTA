# 04 — Ingestion des données : Bridge, fichiers, OCR & justificatifs

> **État au 2026-11-13** (ajouté ; le reste du doc décrit la cible) :
> - Bancaire : synchro Digifactory réelle, idempotente, avec archive brute,
>   quarantaine résolue par le gestionnaire (AXE-424) et contre-passation
>   d'une transaction modifiée (doc 16). Un sous-compte 512x par compte
>   bancaire (AXE-832) ; seuls les comptes retenus sont comptabilisés
>   (AXE-729). Plusieurs comptes Digifactory par portefeuille, un client par
>   jeton (AXE-872). Premier mois réel exporté : AXE-728 et AXE-733. Mois
>   d'avant la connexion Digifactory : AXE-833.
> - La transaction normalisée porte le type d'opération et la catégorie de
>   la banque (AXE-826).
> - Plateformes : revenus lus chez Rollee par période (AXE-818), gardés une
>   fois (`settlements_plateforme`), rapprochés du virement bancaire
>   (AXE-821, doc 13). Une période qui ne tombe pas juste part en quarantaine.
> - Fichiers : aucun profil d'import CSV/Excel générique pour les
>   opérations (le seul import CSV est celui des dossiers, AXE-809, doc 14).
>   Relevés Uber et Bolt en secours de Rollee : AXE-801. Le FEC de l'outil
>   précédent se reprend en bilan d'ouverture (AXE-804, lecteur tolérant aux
>   variantes du format, garde-fous contre un faux FEC).
> - Registres officiels : INSEE et RNE relus chaque semaine pour chaque
>   dossier qui a un SIREN (AXE-849).
> - Justificatifs : stockés en base par tenant et dossier (AXE-425), une
>   photo par dépense. Pas d'OCR, pas de matching automatique, pas de WORM.

> Statut : brouillon à valider — Dernière mise à jour : 2026-09-24

## 1. Principes

1. **Conserver le brut, toujours.** Chaque payload Digifactory (Bridge), chaque
   fichier importé, chaque image de ticket est archivé tel quel (hash SHA-256,
   horodatage, source) avant toute transformation. On peut rejouer n'importe
   quel import.
2. **Idempotence.** Rejouer un import ne crée jamais de doublons. Clé de
   déduplication : `(compte, date, montant, hash(libellé brut), index_intra_jour)` +
   l'ID transaction Digifactory quand il existe. Une transaction déjà
   comptabilisée dont le montant ou la date change, ou qui disparaît, n'est
   pas réécrite : contre-passation et quarantaine (doc 06 I2,
   `workflow/synchro.py`, 2026-09-24).
3. **Le justificatif est optionnel par conception.** Une transaction sans ticket est
   traitée et comptabilisée ; elle porte un statut `piece_manquante` qui alimente la
   liste de relance, jamais un blocage.
4. **Quarantaine plutôt que rejet silencieux.** Toute ligne non parsable part en
   quarantaine avec sa raison, visible dans l'UI, corrigeable, réinjectable.

## 2. Connecteur bancaire : Digifactory (agrégateur Bridge)

> **Pour septembre 2026, le seul canal actif est Digifactory** — pas d'appel
> Bridge direct en parallèle ce mois-ci. Bridge reste la source de données de
> base ; Digifactory n'est qu'un tampon qui agrège les mêmes données par
> contact. Détail complet : doc 16.

- **Rôle** : Bridge est l'AISP (agrégation DSP2) sous-jacent, mais nous n'y
  accédons pas en direct — Digifactory, déjà client Bridge, nous expose une
  API dédiée (`/contacts`, `/accounts/{nr}`, `/transactions/{nr}`,
  `/categories`). Le consentement utilisateur passe par Bridge Connect côté
  Digifactory (qui gère précisément cette relation reste un point ouvert, doc
  16 §6).
- **Abstraction** : interface `DataProvider` (doc 13 §2), implémentée par
  `DigifactoryProvider` (méthodes `fetch_transactions(since)`, `health`).
  Digifactory est la première implémentation active, pas la seule prévue : un
  `BridgeProvider` direct est testé en sandbox après le pilote Digifactory
  (doc 16 §8), sans rien changer à cette interface.
- **Synchronisation** : **pull uniquement**, à notre initiative — pas de
  webhook côté Digifactory. Sync incrémental sur le paramètre `since`
  (filtre `updated_at`), en persistant le `updated_at` max observé par contact
  (doc 16 §3.1). `from`/`to` réservés aux rattrapages ponctuels.
- **Gestion des états** : la combinaison `paused` + `data_access` +
  `last_refresh_status` (exposée par `/accounts/{nr}`) distingue un chauffeur
  inactif d'une connexion cassée. → tableau de bord de santé des connexions
  par dossier + alertes au client (c'est lui qui fait relancer le gérant du
  dossier concerné). La date d'expiration du consentement DSP2 n'est pas
  confirmée exposée par Digifactory — sans elle, relance anticipée J-14
  impossible (doc 14 §2.3, doc 16 §6).
- **Historique limité** : profondeur conservée côté Digifactory non confirmée
  (doc 16 §6). La reprise des données anciennes passe par les imports
  fichiers (§3) — d'où leur statut de fonctionnalité de premier rang, pas de
  mode test.
- **Statut actuel : token en échec (401)**, développement mené contre des
  fixtures en attendant le déblocage (doc 16 §7) — ne pas bloquer le
  développement du provider là-dessus.

## 3. Imports fichiers (CSV, Excel, ODS, OFX, QIF)

### 3.1 Profils d'import

Chaque source de fichier est décrite par un **profil d'import** versionné,
configurable par tenant sans déploiement :

```yaml
# exemple de profil
profil: banque_x_export_csv
encodage: auto-détecté (BOM, chardet) puis figé
separateur: ";"
ligne_entete: 1
colonnes:
  date_operation: { source: "Date opé", format: "DD/MM/YYYY" }
  libelle:        { source: "Libellé" }
  debit:          { source: "Débit",  type: montant_fr }   # "1 234,56"
  credit:         { source: "Crédit", type: montant_fr }
regles:
  montant: credit - debit   # → montant signé en centimes
  ignorer_lignes: ["TOTAL", ""]
```

### 3.2 Pièges à gérer explicitement (et tester un par un)

- Encodages (UTF-8, Latin-1, BOM), montants français (`1 234,56`, parenthèses pour
  négatif), dates ambiguës (`03/04/2025`), colonnes débit/crédit séparées vs montant
  signé, lignes de solde intercalées, cellules fusionnées dans Excel, feuilles
  multiples, formules ODS, fichiers tronqués.
- **Excel/ODS** : lecture via `openpyxl` / `odfpy` (valeurs calculées, jamais les
  formules). Tout fichier est converti vers une table canonique `RawRow[]` avant le
  mapping — un seul chemin de code après le parsing.

### 3.3 Rapport d'import

Chaque import produit un rapport : lignes lues / importées / dédupliquées / en
quarantaine, période couverte, trous de séquence détectés (gap de dates suspect),
delta de solde si le fichier contient des soldes. Ce rapport est montré à
l'utilisateur **avant** confirmation de l'import (étape de prévisualisation).

## 4. Justificatifs : OCR, Vision, Factur-X

### 4.1 Pipeline en cascade (du moins cher au plus cher)

```text
Document reçu (PDF, JPEG, PNG, HEIC)
  │
  ├─ 1. PDF avec texte natif ? → extraction directe (pdfplumber). Coût ~0.
  ├─ 2. Factur-X / facture électronique ? → lire le XML embarqué. Fiabilité maximale.
  ├─ 3. OCR open-source (Tesseract ou PaddleOCR) + parsing structuré.
  │     → suffisant pour les factures propres ; benchmark à faire (ADR-005).
  └─ 4. Vision LLM (Claude/GPT-4V/Gemini) en dernier recours :
        tickets froissés, photos de mauvaise qualité, mises en page exotiques.
        Image transmise après masquage des zones sensibles si identifiables,
        extraction en JSON schema strict.
```

Champs extraits : commerçant, SIRET si présent, date, montant TTC, TVA par taux,
moyen de paiement, nature des articles (pour la détection d'abus : un ticket Auchan
listant des courses alimentaires ≠ un ticket Auchan carburant).

Chaque extraction porte un **score de confiance par champ** ; en dessous du seuil,
le champ est marqué `à vérifier` dans l'UI (jamais inventé).

### 4.2 Matching justificatif ↔ transaction

Algorithme de rapprochement scoré :

| Critère | Poids |
|---------|-------|
| Montant exact (± tolérance pourboire/arrondi configurable) | fort |
| Date à ±3 jours (délai de débit carte) | moyen |
| Commerçant ↔ libellé bancaire (similarité fuzzy + dictionnaire d'enseignes) | moyen |
| Moyen de paiement cohérent | faible |

- Score ≥ seuil haut → matching automatique (réversible).
- Zone grise → file de matching manuel (UI à deux colonnes, doc 11).
- Aucun match → le justificatif reste en « orphelins », la transaction reste
  `piece_manquante`. Les deux vivent leur vie.

### 4.3 Canaux d'entrée des justificatifs

V1 : upload via l'interface B2B (le client gestionnaire centralise) + **adresse
email dédiée par dossier** (les gérants — chauffeurs ou autres — transfèrent leurs
factures par mail, réaliste vu qu'ils n'ont pas accès à la plateforme ; en mode
mono-entreprise, c'est l'entreprise elle-même qui uploade). Phase 2 : API pour
intégrations tierces.

## 5. Normalisation : la sortie unique du module

Quel que soit le canal (Digifactory, CSV, Excel...), le module émet le même objet :

```python
class NormalizedTransaction(BaseModel):
    id: TransactionId
    dossier_id: DossierId
    compte_bancaire_id: CompteBancaireId
    date_operation: date
    date_valeur: date | None
    montant_centimes: int            # signé : négatif = débit
    devise: Literal["EUR"]           # V1 : EUR uniquement, élargir plus tard
    libelle_brut: str                # jamais modifié
    libelle_nettoye: str             # casse, espaces, codes banque retirés
    source: Literal["digifactory", "import_fichier"]  # "bridge" viendra avec le provider direct (doc 16 §8)
    source_ref: str                  # ID transaction Digifactory ou (fichier, ligne)
    hash_dedup: str
    statut_piece: Literal["matchee", "manquante", "non_requise"]
```

Le nettoyage de libellé (suppression des préfixes banque type `CB****1234`,
extraction de la date embarquée, du nom d'enseigne) est **déterministe, versionné et
testé** : c'est la matière première du ML, sa stabilité conditionne tout l'aval.

## 6. Tests spécifiques au module (résumé, détail doc 09)

- Corpus de fichiers réels anonymisés par banque/format, en fixtures versionnées.
- Tests de propriété (Hypothesis) sur le parsing des montants et dates.
- Test d'idempotence : tout import rejoué deux fois = zéro doublon.
- Test de quarantaine : un fichier corrompu n'interrompt jamais les lignes valides.
- Golden tests OCR : N tickets de référence → extraction attendue figée.
