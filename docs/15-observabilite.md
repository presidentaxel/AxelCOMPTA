# 15 — Observabilité, métriques et monitoring

> **État au 2026-11-05** (ajouté) : `GET /metrics` au format Prometheus,
> journal JSON structuré et Sentry si `SENTRY_DSN` est posé (AXE-426).
> Pas encore : dashboards, alerting, métriques métier (taux de
> catégorisation, coût LLM), contrôle quotidien de la balance (AXE-807).

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-16

L'observabilité d'AxeLCompta a deux finalités distinctes qu'il ne faut pas mélanger :
1. **Métriques métier** — mesurer les KPIs du doc 01 en production (taux de catégorisation, recours LLM, précision…)
2. **Métriques techniques** — garantir que le système fonctionne (latence, mémoire, erreurs, jobs)

## 1. Stack d'observabilité

| Couche | Outil | Usage |
|--------|-------|-------|
| Erreurs applicatives | **Sentry** | Exceptions non gérées, invariants violés, alertes critiques |
| Logs structurés | **structlog** (Python) + **JSON** | Audit trail, debugging, conformité |
| Métriques | **Prometheus** + **Grafana** | KPIs métier + métriques techniques |
| Métriques DB | **Supabase dashboard** | Connexions, requêtes lentes, taille des tables |
| APM (option) | **Sentry Performance** | Traces distribuées, latence par endpoint |

Pas de stack observabilité complexe en V1 — Sentry + logs JSON couvrent 90% des besoins. Prometheus/Grafana s'ajoutent quand les KPIs doivent être suivis en continu (avant le pilote client).

## 2. Métriques métier (KPIs doc 01 — mesurés en production)

Ces métriques prouvent que le produit fonctionne. Chacune a un seuil cible et déclenche une action si dépassé.

| Métrique | Seuil cible V1 | Seuil d'alerte | Action si alerte |
|----------|---------------|----------------|-----------------|
| `categorization.rate.rule` | ≥ 60 % des transactions | < 50 % | Ajouter des règles système dans le pack |
| `categorization.rate.ml` | ~30 % | — | Indicatif |
| `categorization.rate.llm` | ≤ 10 % | > 15 % | Coût LLM explose — miner de nouvelles règles |
| `categorization.rate.human` | ≤ 5 % | > 10 % | ML à réentraîner ou seuil à ajuster |
| `categorization.precision` | ≥ 97 % | < 95 % | Audit des labels, réentraînement |
| `anomaly.recall` | ≥ 80 % | < 75 % | Détecteurs à calibrer |
| `ledger.balance_error` | **0** toujours | > 0 | **Alerte critique immédiate** — invariant I1 |
| `fec.validation_error` | **0** | > 0 | **Alerte critique** — FEC non conforme |
| `transaction_to_entry.p95` | < 48 h | > 72 h | Pipeline trop lent ou file bouchée |
| `settlement.unreconciled_rate` | < 5 % | > 10 % | Problème Rollee ou Digifactory |
| `consent.expiry_rate` | < 5 % des dossiers | > 10 % | Campagne de renouvellement urgente |

Ces métriques sont exposées comme compteurs/gauges Prometheus depuis le backend et affichées dans Grafana.

## 3. Métriques techniques

### 3.1 API et workers

```
http.request.duration_ms{endpoint, method, status}   # latence par endpoint (p50, p95, p99)
http.request.count{endpoint, status}                  # volume et taux d'erreur
job.queue.depth{job_type}                             # profondeur de la file de jobs
job.duration_ms{job_type}                             # temps d'exécution par type
job.error.count{job_type, error_type}                 # échecs par type
worker.memory_mb{worker_id}                           # consommation mémoire
```

### 3.2 Modèles ML (surveillance spécifique)

Les modèles scikit-learn / LightGBM sont chargés au démarrage du worker. Ils peuvent peser 50-500 Mo selon la taille du vocabulaire TF-IDF.

```
ml.model.load_duration_ms{model_name}                 # temps de chargement au démarrage
ml.model.memory_mb{model_name}                        # empreinte mémoire du modèle
ml.inference.duration_ms{model_name}                  # latence de prédiction
ml.inference.confidence{model_name, category}          # distribution des scores (dérive)
ml.model.version{model_name}                          # version du champion en production
```

**Seuils mémoire :** si `worker.memory_mb` dépasse 1 Go en prod, envisager un worker ML dédié séparé du worker principal. À mesurer sur les premières semaines de pilote.

### 3.3 Providers externes (Digifactory, Rollee, LLM)

```
provider.digifactory.latency_ms                       # latence API Digifactory (canal actif — doc 16)
provider.digifactory.error.count{error_type}           # erreurs (401 = auth invalide/token révoqué, doc 16 §7 ; sinon consentement expiré)
provider.rollee.latency_ms
provider.rollee.error.count{error_type}
llm.call.count{provider, model}                       # volume d'appels LLM
llm.call.duration_ms{provider}                        # latence LLM
llm.call.tokens{provider, direction}                  # tokens in/out (coût)
llm.call.cost_eur{provider, tenant_id}                # coût en euros par tenant (budget)
llm.cache.hit_rate                                    # taux de cache libellés-types
```

Le coût LLM par tenant est la métrique la plus importante financièrement — un tenant qui consomme disproportionnellement doit déclencher une revue des règles pour son pack.

### 3.4 Base de données (Supabase dashboard + alertes)

Métriques à surveiller dans le dashboard Supabase :
- Connexions actives (pool épuisé = latence API)
- Requêtes lentes > 1 s (index manquant probable)
- Taille des tables `transactions` et `journal_entries` (croissance mensuelle)
- Taille totale de la base (quota Supabase Pro : 8 Go)

Requête à scheduler quotidiennement pour vérifier l'invariant I7 :
```sql
-- Balance générale : doit retourner 0 pour chaque dossier
SELECT dossier_id, SUM(CASE WHEN sens = 'D' THEN montant_cts ELSE -montant_cts END) AS solde
FROM lignes_ecriture
JOIN ecritures USING (ecriture_id)
WHERE ecritures.statut = 'validee'
GROUP BY dossier_id
HAVING ABS(SUM(CASE WHEN sens = 'D' THEN montant_cts ELSE -montant_cts END)) > 0;
-- Résultat attendu : 0 lignes. Toute ligne = alerte critique Sentry.
```

## 4. Logs structurés — format et règles

### 4.1 Format JSON obligatoire

Chaque log est un objet JSON avec les champs suivants :

```json
{
  "timestamp": "2026-01-15T10:23:45.123Z",
  "level": "info",
  "module": "categorize.pipeline",
  "trace_id": "abc123",
  "tenant_id": "ten_xxx",
  "dossier_id": "dos_yyy",
  "event": "transaction.categorized",
  "source": "rule",
  "rule_id": "rule-fuel-total-001",
  "confidence": 1.0,
  "duration_ms": 3
}
```

### 4.2 Ce qui DOIT être loggué

| Événement | Niveau | Pourquoi |
|-----------|--------|----------|
| Validation humaine d'une écriture | `info` | Audit trail réglementaire |
| Décision LLM (catégorie + justification courte) | `info` | Audit + boucle d'amélioration |
| Invariant comptable violé | `critical` | → Sentry immédiatement |
| Consentement DSP2/Rollee expiré | `warning` | Relance à déclencher |
| Import réussi (N transactions) | `info` | Traçabilité ingestion |
| Alerte anomalie ouverte | `info` | Audit + statistiques |
| Clôture d'exercice (début/fin) | `info` | Audit réglementaire |
| Appel LLM (sans le contenu du prompt) | `info` | Coût + dérive |

### 4.3 Ce qui NE DOIT PAS être dans les logs (PII)

**Règle absolue :** aucune donnée personnelle nominative dans les logs applicatifs.

```python
# INTERDIT dans les logs
logger.info("Transaction reçue", libelle="VIR M. JEAN MARTIN", montant=84732)
logger.info("Chauffeur connecté", nom="Jean Martin", iban="FR76...")

# CORRECT — identifiants opaques uniquement
logger.info("transaction.received", transaction_id="txn_xxx", dossier_id="dos_yyy", montant_cts=84732)
logger.info("driver.connected", account_id="drv_zzz", provider="rollee")
```

Un lint custom (ruff rule ou pre-commit hook) détecte les appels de log contenant des champs suspects (`libelle`, `nom`, `prenom`, `iban`, `email`, `siret`). Bloquant en CI.

### 4.4 Rétention des logs

- Logs applicatifs : 12 mois (sans PII — conforme RGPD, doc 10 §3)
- Logs d'audit métier (validation, clôture) : 10 ans (obligation légale — stockés séparément en base append-only, pas dans les logs applicatifs)

## 5. Alerting — niveaux et destinataires

| Niveau | Exemples | Canal | Délai de réponse |
|--------|----------|-------|-----------------|
| **Critical** | Invariant comptable violé, FEC non conforme, fuite PII détectée | Sentry + SMS | < 1 h |
| **Error** | Panne Digifactory/Rollee > 15 min, job échoué 3 fois, import rejeté | Sentry + email | < 4 h |
| **Warning** | Taux LLM > 15 %, consentement expiré, balance check échoué (job quotidien) | Email digest | < 24 h |
| **Info** | KPIs hebdomadaires, rapport d'import, clôture terminée | Dashboard | Passif |

En V1 avec 1-2 devs : les alertes Critical et Error vont sur le téléphone. Les Warning dans un email digest quotidien. Pas de PagerDuty ni d'astreinte formelle avant le pilote.

## 6. Dashboard Grafana — panels recommandés

**Vue "Santé du pipeline" (quotidienne) :**
- Distribution catégorisation par source (règle/ML/LLM/humain) — graphique en aires empilées
- Taux de recours LLM par tenant — bar chart
- Settlements non réconciliés en attente — gauge
- Consentements expirant dans 14 jours — compteur

**Vue "Moteur comptable" (permanente) :**
- Balance check : vert = 0 erreur, rouge = nombre d'erreurs — gauge binaire
- FEC validations en CI : derniers résultats
- File de jobs : profondeur par type

**Vue "Coûts LLM" (hebdomadaire) :**
- Coût LLM total en euros par semaine
- Coût par tenant (détecter les outliers)
- Taux de cache hit (économies réalisées)

## 7. Surveillance de la dérive ML

Le modèle de catégorisation doit être monitoré en continu pour détecter une dérive (les données de production s'éloignent des données d'entraînement).

Indicateurs de dérive à surveiller :
- **Taux de correction humaine par classe** : si une classe passe de 2 % à 10 % de corrections, le modèle a régressé sur cette classe
- **Distribution des scores de confiance** : si la médiane des scores ML descend de 0,92 à 0,78, la dérive est là
- **Taux d'escalade LLM par catégorie** : une catégorie qui escalade souvent = lacune dans les règles ou le ML

Ces indicateurs sont calculés hebdomadairement par un job dédié (`ml/monitoring.py`) et alimentent le rapport de réentraînement mensuel (doc 07 §5).
