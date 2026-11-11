# 13 — Intégrations de plateformes et pattern DataProvider

> **État au 2026-11-10** (ajouté) : la réconciliation et les écritures de
> settlement (§4, §5) sont codées et testées sur fixtures (golden test
> §5.3, autoliquidation Bolt). Rollee n'est pas contractualisé. Tickets
> ouverts le 05/11 (AXE-440, qui les regroupait, est annulé) : AXE-817
> (contrat, sandbox, User API ou Company API), AXE-818 (client et
> `RolleeProvider`), AXE-819 (Rollee Connect), AXE-820 (webhooks signés,
> synchro de secours), AXE-821 (réconciliation avec le virement
> Digifactory, écritures 706, TVA et commission). En attendant, les
> settlements viendront des relevés exportés par le chauffeur depuis Uber
> et Bolt (AXE-801).

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
| Heetch (France) | TVA 20% française | Déductible normalement |

Cette configuration vit dans le **pack VTC** (`packs/vtc/platforms.yaml`), pas dans le code. Ajouter une plateforme = ajouter une ligne de config.

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
