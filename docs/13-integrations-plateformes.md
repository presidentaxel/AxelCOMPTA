# 13 — Intégrations de plateformes et pattern DataProvider

> **État au 2026-11-16** (ajouté ; le reste du doc décrit la cible
> d'origine, dont le modèle « une période = un virement » du §4, remplacé) :
> Rollee tourne sur la base réelle depuis le 14/11 (pilote sur les
> chauffeurs de Serenity).
>
> **Accès et liens**
> - AXE-817, AXE-872 : accès par le compte Rollee de Serenity, API
>   utilisateur, un **branchement** par compte, jeton chiffré. Un jeton
>   renouvelé est toujours gardé (`garder_parametre`).
> - AXE-818, AXE-820 : client (JWT renouvelé, 429 et 5xx réessayés),
>   webhooks signés (HMAC SHA-512) et rattrapage quotidien. Montants en
>   euros, vérifié sur la prod.
> - AXE-819 : le chauffeur relie ses comptes dans Rollee Connect (§3.3).
> - Relier un user Rollee à son dossier (AXE-911, puis #170, AXE-917 à
>   923) : la synchro compare `GET /users` à une **carte** en base
>   (`cartes_rollee`) et un job `rapprochement_rollee` lit les users
>   nouveaux ou changés. Empreintes HMAC (metadata, nom avec e-mail ou
>   téléphone), l'IBAN n'est plus lu. Un nom unique sur la carte relie tout
>   seul ; sinon le gestionnaire choisit, ou cherche par le nom (nom en
>   clair, e-mail masqué, jamais de montant).
> - Un chauffeur peut avoir plusieurs comptes Rollee, et un user « flotte »
>   porter ceux de plusieurs chauffeurs : le lien garde les **noms attendus**
>   du dossier, seuls les comptes à ce nom sont retenus (§3.1).
> - Le bouton Synchroniser du portefeuille relit Rollee pour chaque dossier
>   relié, après Digifactory, un dossier à la fois (AXE-929).
>
> **Revenus (AXE-924, remplace le modèle d'AXE-821)**
> - Rollee renvoie des jours, des semaines et des mois qui se chevauchent :
>   **seuls les jours comptent**. Le gagné d'un jour est `net_amount`
>   (brut − commission) ; `payouts` est un retrait, pas le gagné. Tout
>   l'historique est lu (depuis 2020, AXE-928).
> - Les **espèces** (`cash_earnings`, toutes plateformes) ne passent pas
>   par la banque : dû par la plateforme = gagné − espèces.
> - **Uber verse chaque lundi via POP SVCS** la semaine précédente (période
>   dans le libellé) ; en cours de semaine, des **virements instantanés**
>   (« Stichting Custodian Uber Payments ») à 0,99 € de frais, pas
>   toujours. Bolt verse le lundi (« BOLT FR »). Free Now : « TRANSCOVO SAS
>   FREENOW », semaine lue dans le libellé (AXE-933).
> - Contrôle **par semaine** (`ingestion/semaines_plateforme.py`) : soldée
>   si l'écart est nul ou vaut k × 0,99 € (k ≤ nombre d'instantanés),
>   éventuellement cumulée avec la semaine d'avant ; en attente 8 jours ;
>   sinon **à vérifier**, avec les frais et l'écart chiffrés (AXE-932). Rien
>   n'est écrit pour une semaine qui ne retombe pas juste.
>
> **Écritures d'une semaine soldée** (`ingestion/ecritures_semaines.py`,
> schéma de l'expert-comptable, AXE-931)
> - Chaque jour : recette contre une **créance par plateforme** (4671 Uber,
>   4672 Bolt, 4673 Heetch, 4674 Allocab, 4675 Free Now ; 467 pour une
>   autre), espèces en **530 Caisse**, courses en 706 HT + 44571 (10 %),
>   commission en **6222** (autoliquidation Bolt en 44566/44571, lue par la
>   CA3).
> - **Seules les courses portent la TVA** (AXE-926) : pourboires (`tips`),
>   bonus (`bonus_amount`) et autres montants (`other_amount`) vont en
>   **708**, sans TVA. Le reste du brut que Rollee ne classe pas garde la
>   TVA, par prudence.
> - Chaque virement solde la créance (sa contrepartie 471 ou 706 est
>   vidée, le 512 ne bouge pas) ; les frais d'instantanés vont en 627.
> - Les semaines écrites avant AXE-931 (467, 455, 7068, 622) sont reprises
>   par une OD `{S}:comptes-plateforme` (appliquée en prod le 15/11).
> - Retirer un lien Rollee contre-passe toutes les écritures des semaines
>   concernées.
> - La commission Uber vaut 0 chez Rollee : le CA Uber est pris après
>   commission tant que Rollee ne la donne pas (AXE-939).
>
> **Rollee ↔ banque et ce qui manque**
> - La banque fait foi pour la compta (une semaine n'est écrite que si ses
>   virements sont trouvés). Tout l'historique Rollee est comparé à la
>   banque, par mois et par semaine (AXE-928,
>   `ingestion/comparaison_rollee.py`, écran du chauffeur) : rapprochée,
>   pas de relevé bancaire, virement manquant, versé en trop, payée mais
>   absente de Rollee. Les années sans banque servent de rapport.
> - Mode expert, « Rapprochements Rollee » (AXE-925, `explication_semaines.py`)
>   : par semaine, dû, payé, frais, écart, jours et virements. En tête, « Ce
>   qui manque pour tout rapprocher » (AXE-934, `manques_rollee.py`).
> - Reste : sortir une semaine de « à vérifier » (AXE-912) ; relevés CSV
>   Uber et Bolt pour un chauffeur sans Rollee (AXE-801).

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-16

## 1. Le problème : deux types de données d'entrée distincts

Pour un dossier VTC, les données arrivent de deux sources orthogonales qui doivent être réconciliées :

| Source | Ce qu'elle fournit | Type interne |
|--------|-------------------|--------------|
| **Digifactory** (agrégateur Bridge, API bancaire — doc 16) | Les mouvements du compte bancaire du chauffeur : virements entrants (Uber, Bolt...), débits (carburant, péages...) | `NormalizedTransaction` |
| **Rollee** (API plateformes) | Le détail des courses et revenus sur chaque plateforme : brut, commission, TVA, net versé | `PlatformSettlement` |

Un virement bancaire `+847,32 € - UBER BV AMSTERDAM` ne permet pas, seul, de générer les écritures correctes (ventilation 706 / 622 / 44571 / 44566). Il faut le croiser avec le relevé Rollee de la même semaine, qui décompose ce montant.

**C'est la réconciliation `PlatformSettlement` ↔ `NormalizedTransaction` (banque) qui produit l'écriture complète.** Sans cette réconciliation, on génère une écriture approximative à corriger manuellement.

## 2. Pattern DataProvider — architecture

### 2.1 Principe

Le module `ingestion/` expose une interface abstraite `DataProvider`. Chaque source de données est une implémentation. La configuration du tenant détermine quels providers sont actifs — jamais de branchement conditionnel dans le code métier.

```
ingestion/
├── providers/
│   ├── base.py              # ABC DataProvider + types partagés
│   ├── digifactory.py       # DigifactoryProvider (transactions bancaires, agrège Bridge — doc 16)
│   ├── rollee.py            # RolleeProvider (données plateformes gig)
│   └── file_import.py       # FileImportProvider (CSV/XLSX/ODS/OFX)
├── reconciliation.py        # Matching PlatformSettlement ↔ NormalizedTransaction
└── normalizer.py            # Nettoyage et normalisation des libellés
```

### 2.2 Interface DataProvider

```python
# ingestion/providers/base.py
from abc import ABC, abstractmethod
from core.types import DossierId, TenantId

class DataProvider(ABC):
    """Contrat unique pour toute source de données d'entrée."""

    @abstractmethod
    async def fetch_transactions(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        since: date,
        until: date,
    ) -> list[NormalizedTransaction]:
        """Transactions bancaires normalisées."""

    @abstractmethod
    async def fetch_platform_settlements(
        self,
        tenant_id: TenantId,
        dossier_id: DossierId,
        since: date,
        until: date,
    ) -> list[PlatformSettlement]:
        """Relevés de plateformes (Uber, Bolt...). Peut retourner [] si non supporté."""

    @abstractmethod
    async def health(self) -> ProviderHealth:
        """Santé de la connexion (consentement valide, quota restant...)."""
```

### 2.3 Configuration par tenant

```python
# Dans la config dossier (table dossier_config)
{
  "providers": {
    "bank": "digifactory",      # digifactory | bridge | file_import
    "platforms": "rollee",      # rollee | file_import | none
  },
  "rollee": {
    "fleet_account_id": "fleet_abc123",
    "driver_account_id": "drv_xyz789"
  },
  "digifactory": {
    "contact_nr": "12345"
  }
}
```

Le provider `digifactory` alimente les transactions bancaires (canal actif pour le pilote — doc 16). Un provider `bridge` direct suivra le même contrat quand le sandbox sera testé (doc 16 §8). Le provider `rollee` alimente les settlements de plateformes. Les deux coexistent sur le même dossier. Un dossier sans Rollee (client futur hors VTC) passe sur `platforms: none` ou `file_import`.

**Règle impérative :** le code de `categorize/`, `ledger/`, `anomaly/` ne doit jamais importer `rollee.py` ni `digifactory.py` (ni `bridge.py` le jour où il existera). Il reçoit des `NormalizedTransaction` et des `PlatformSettlement` — point.

## 3. Rollee — intégration concrète

### 3.1 Ce qu'est Rollee

[Rollee](https://getrollee.com) est un agrégateur de données de l'économie de plateforme (Uber, Bolt, Wolt, Deliveroo, Heetch…). Il expose une API REST standardisée et fournit deux modes :

- **Mode B2C** : le chauffeur s'authentifie lui-même via Rollee Connect (SDK web/mobile).
- **Mode B2B fleet** : la flotte (le client gestionnaire) gère un compte admin et invite ses chauffeurs en masse. **C'est le mode utilisé pour le client pilote.** Le gestionnaire a accès aux données agrégées de tous ses chauffeurs depuis un seul compte fleet.

Les comptes « flotte » (`uber.com-fleet-rev`, `bolt.eu-fleet-rev`, `allocab-fleet-rev`) n'ont dans leur profil que `full_name`, jamais `first_name` / `last_name`. Le rapprochement lit ce nom. Un même user Rollee peut porter les comptes de plusieurs chauffeurs : le lien garde les empreintes de nom du dossier, et seul le compte à ce nom est retenu. Les autres ne sont ni reliés, ni stockés, ni montrés, et leurs revenus ne sont pas lus (AXE-923). Un user créé depuis l'espace du chauffeur (`cree`) n'a pas de noms attendus : tous ses comptes sont à lui.

Les plateformes reconnues sont dans `_AUDIT_DONNEES/packs_vtc/plateformes.csv` : Uber, Bolt, et depuis le 15/11 Heetch, Allocab et Free Now (AXE-933). Les jours d'une plateforme absente de ce fichier partent en quarantaine (« plateforme absente »).

### 3.2 Données disponibles via l'API Rollee

| Endpoint | Données retournées | Usage AxeLCompta |
|----------|-------------------|-----------------|
| `GET /accounts` | Liste des comptes chauffeur rattachés à la flotte | Vérification que tous les dossiers ont un compte Rollee |
| `GET /accounts/{id}/income` | Revenus par période : brut, commission, net, par plateforme | Base des écritures 706 + 622 |
| `GET /accounts/{id}/trips` | Courses individuelles avec montants | Granularité pour audit ; agrégées pour comptabilité |
| `GET /accounts/{id}/wallet` | Virements reçus (date, montant, plateforme) | Clé de réconciliation avec Digifactory (Bridge) |
| `GET /accounts/{id}/performance` | Statistiques activité | Profil comportemental du dossier (doc 07 §3.3) |

### 3.3 Flux de connexion d'un chauffeur (mode fleet)

```
Client gestionnaire (AxeLCompta) ──► crée une session Rollee Connect
                                       (email d'invitation au chauffeur)
Chauffeur ──► ouvre le lien ──► s'authentifie sur ses comptes Uber/Bolt
                                ──► accorde les permissions
Rollee ──► webhook "account.connected" ──► AxeLCompta stocke l'account_id
AxeLCompta ──► appel quotidien GET /accounts/{id}/income + wallet
           ──► webhook "wallet.payout_received" pour les mises à jour temps réel
```

La connexion est renouvelable. Rollee notifie en avance une expiration de token (même concept que Bridge pour les consentements DSP2). Voir doc 15 §2.3 pour la gestion des renouvellements.

### 3.4 Polling vs webhooks

- **Webhooks** (à privilégier) : Rollee envoie un événement `wallet.payout_received` à chaque nouveau virement. AxeLCompta déclenche immédiatement l'import et la tentative de réconciliation.
- **Polling quotidien** : fallback si le webhook est manqué. Le job daily vérifie pour chaque dossier si de nouveaux données sont disponibles depuis le dernier import.

Les deux sont nécessaires (idempotence obligatoire : rejouer un import deux fois = zéro doublon).

## 4. Réconciliation Settlement ↔ Transaction bancaire

### 4.1 Le type `PlatformSettlement`

```python
@dataclass(frozen=True)
class PlatformSettlement:
    id: SettlementId
    dossier_id: DossierId
    platform: str                    # "uber" | "bolt" | "heetch" | ...
    period_start: date
    period_end: date
    payout_date: date
    gross_earnings_cts: int          # centimes, TTC si chauffeur assujetti TVA
    commission_cts: int              # centimes, montant prélevé par la plateforme
    commission_tva_regime: str       # "france_20" | "autoliquidation_ue" | "exonere"
    net_payout_cts: int              # = ce qui doit arriver en banque
    currency: str                    # "EUR"
    source_provider: str             # "rollee"
    raw_payload: dict                # payload brut archivé (immuable)
```

### 4.2 Algorithme de matching

```
Pour chaque PlatformSettlement reçu :
  1. Chercher une NormalizedTransaction bancaire dont :
     - montant == settlement.net_payout_cts  (±1 centime pour arrondi)
     - date ∈ [settlement.payout_date - 3j, settlement.payout_date + 5j]
     - libellé contient le nom de la plateforme (heuristique)
  2. Si match unique → lier les deux (settlement_id sur la transaction)
     → éligible à la génération automatique des écritures (§5)
  3. Si pas de match → settlement en attente, alerte "transaction bancaire attendue"
  4. Si match multiple → file de revue humaine
```

Le délai ±3j/+5j couvre les décalages de virement inter-banques. La tolérance de 1 centime couvre les arrondis de conversion.

### 4.3 États d'un settlement

```
rollee_reçu → en_attente_banque → réconcilié → écritures_générées → validé
                     ↑                  ↑
           digifactory_reçu_avant   digifactory_reçu_après
```

Un settlement peut rester en `en_attente_banque` plusieurs jours (le virement Uber peut prendre 3 à 5 jours ouvrés). C'est normal — ce n'est pas une alerte tant que la fenêtre n'est pas dépassée.

## 5. Génération d'écritures depuis un settlement réconcilié

### 5.1 TVA sur les recettes VTC — principe de flexibilité

La TVA sur les prestations de transport est **configurable par dossier**, pas codée en dur. Les options :

| Régime | Quand | TVA collectée |
|--------|-------|--------------|
| `assujetti_taux_reduit` | Chauffeur assujetti, transport de personnes | 10% sur recettes HT |
| `franchise` | Chauffeur sous seuil franchise TVA | 0% (montant brut = HT) |

Ce paramètre est dans la configuration du dossier (`tva_recettes_regime`). Le moteur lit cette configuration — **jamais de `if regime == "franchise"`** éparpillé dans le code.

### 5.2 TVA sur les commissions de plateforme — configurable par plateforme

Les commissions prélevées par Uber/Bolt sont des achats de services. La TVA applicable dépend de l'entité facturante :

| Plateforme (entité facturante) | Régime TVA commission | Récupération |
|-------------------------------|----------------------|--------------|
| Uber France SAS (France) | TVA 20% française | Déductible normalement |
| Bolt Operations OÜ (Estonie, UE) | Autoliquidation UE (art. 283-2 CGI) | Déductible en autoliquidation |
| Heetch SAS (France) | TVA 20% française | Déductible normalement |
| Allocab SAS (France) | TVA 20% française | Déductible normalement |
| Free Now (Transcovo SAS, France) | TVA 20% française | Déductible normalement |

Cette configuration vit dans le **pack VTC** (`_AUDIT_DONNEES/packs_vtc/plateformes.csv`, colonne `commission_tva_regime`), pas dans le code. Ajouter une plateforme = ajouter une ligne de config.

### 5.3 Template d'écriture — settlement réconcilié

Exemple : settlement Uber semaine du 09/06, 50 courses.
Dossier en SASU IS, assujetti TVA au réel (taux recettes = 10%), entité Uber France (commission TVA 20%).

```
Données Rollee :
  gross_earnings : 1 040,00 € TTC
  commission     :   192,00 € TTC (Uber France, TVA 20% incluse)
  net_payout     :   848,00 €  ← doit matcher le virement bancaire (Digifactory)

Calculs :
  Recettes HT     = 1 040,00 / 1,10 = 945,45 €
  TVA collectée   = 1 040,00 - 945,45 = 94,55 €
  Commission HT   = 192,00 / 1,20 = 160,00 €
  TVA commission  = 192,00 - 160,00 = 32,00 €

Vérification : 945,45 + 94,55 - 160,00 - 32,00 = 848,00 € = net_payout ✓

Écritures :
  512   Banque                        D   848,00
  622x  Commissions plateformes       D   160,00
  44566 TVA déductible sur commission D    32,00
  706   Prestations de services       C   945,45
  44571 TVA collectée (10%)           C    94,55
                                    ─────────────
                                    1 040,00 = 1 040,00 ✓
```

**Cas franchise TVA :**
```
  gross_earnings = 1 040,00 € (pas de TVA collectée)
  commission     =   192,00 € TTC → non récupérable (franchise)
  net_payout     =   848,00 €

  512   Banque                        D   848,00
  622x  Commissions plateformes       D   192,00   ← TTC car non récupérable
  706   Prestations de services       C 1 040,00
                                    ─────────────
                                    1 040,00 = 1 040,00 ✓
```

**Cas autoliquidation (Bolt) :**
```
  Commission HT Bolt = 160,00 € (pas de TVA facturée par Bolt)
  Autoliquidation : on génère simultanément TVA déductible ET TVA due :
  44566 TVA déductible (autoliquidation)  D  32,00
  44571 TVA due (autoliquidation)         C  32,00   ← s'annulent, net = 0
  → impact nul sur la trésorerie mais obligatoire pour la CA3
```

Chaque variante est un template de données dans `packs/vtc/`, pas une branche de code.

## 6. Settlement sans Rollee (mode dégradé ou client sans Rollee)

Pour un client futur sans Rollee, ou en attendant que le chauffeur connecte son compte :

1. La transaction bancaire `+848,00 € UBER BV` arrive via Digifactory.
2. Sans PlatformSettlement associé, le pipeline de catégorisation la traite comme une recette globale.
3. Écriture simplifiée : `512 D 848,00 / 706 C 848,00` (montant brut, sans ventilation commission).
4. Statut : `catégorisation_partielle` — un flag indique que la ventilation TVA complète est manquante.
5. Quand Rollee est activé plus tard et les données importées, le système peut **rejouer** la réconciliation et enrichir les écritures (counter-passation + nouvelle écriture complète).

Ce mode dégradé permet de ne jamais bloquer — le dossier avance, la précision s'améliore avec le temps.

## 7. Autres plateformes et extensibilité

Le pack VTC V1 couvre Uber et Bolt (les deux plateformes du pilote). Chaque nouvelle plateforme = une ligne dans `packs/vtc/platforms.yaml` avec :
- `name` (identifiant)
- `display_name` (UI)
- `tva_commission` (régime TVA de leur commission)
- `earnings_tva` (taux appliqué aux recettes, si la plateforme ne le donne pas)
- `rollee_platform_key` (identifiant Rollee si supporté)
- `file_import_profile` (profil d'import CSV si Rollee ne supporte pas encore la plateforme)

Si Rollee ne supporte pas une plateforme, on bascule sur l'import CSV du relevé de la plateforme via `FileImportProvider`. Le template d'écriture reste identique — seul le provider change.
