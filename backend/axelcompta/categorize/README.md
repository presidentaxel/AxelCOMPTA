# categorize/

Pipeline de catégorisation hybride en étages : règles dures → modèle ML →
LLM arbitre → revue humaine. Produit des `ProposedEntry` — seul `workflow`
peut les transformer en écritures réelles via `ledger`, après validation
(règle de dépendance CI, doc 03 §3).

**Dépendances :** `core`, `packs`, `ingestion` (types `NormalizedTransaction` en
entrée, doc 13 §2.2), `documents` (matching pièce, V1 seulement).
**N'a pas le droit d'écrire dans `ledger` directement.**

## Les 4 étages (V1, doc 05 §1)

1. **Règles dures** — déterministe, biais maîtrisé (regex du pack).
2. **Modèle ML** — TF-IDF + régression logistique / gradient boosting sur ce
   que les règles ne couvrent pas.
3. **LLM arbitre** — cas ambigus restants, via pseudonymisation en amont
   (doc 10 §4).
4. **Revue humaine** — filet final, explicabilité de bout en bout (doc 05 §7).

## Ce qui existe déjà et sera réutilisé

- [`_AUDIT_DONNEES/modeles/tfidf_logreg_v1.joblib`](../../../_AUDIT_DONNEES/modeles/) —
  79,5% d'exactitude (libellé + bucket de montant, mesurée contre les labels
  du mapping, pas une relecture humaine ; le 94,4% d'ADR-007 utilisait le
  compte PCG, indisponible à l'inférence, voir l'amendement du 2026-09-21),
  **aucun réentraînement nécessaire** pour la démo.
- [`_AUDIT_DONNEES/resultats/fec_ml_taxonomie.csv`](../../../_AUDIT_DONNEES/resultats/) —
  36 152 lignes labellisées, déjà rejoué par `FileImportProvider` (chemin C,
  `ingestion/providers/file_import.py`, fait en semaine 1).

## Fichiers

- `models.py` — `ProposedEntry`, `Etage`.
- `pipeline.py` — `CategorizationPipeline`, façade abstraite.
- `ml_fallback.py` — charge `tfidf_logreg_v1.joblib` comme artefact (jamais
  `import axelcompta.ml`, doc 03 §3), reproduit exactement le featurizing de
  `entrainer_modele_baseline.py` (bucket de montant + libellé). Dégradation
  explicite si le fichier est absent (`ModeleMlIndisponible`, gitignoré).
- `rules_and_ml.py` — `RulesAndMlPipeline` (**fait, semaine 2**) : étage 1
  (première règle du pack qui matche) puis étage 2 (ML si aucune règle ne
  matche, ou catégorie par défaut à confiance nulle si le modèle est absent).

## Étage ML : ce qui est garanti (2026-09-27)

- **Signe** : le modèle a appris en convention FEC (charge positive), la
  transaction arrive en convention bancaire (encaissement positif) ;
  `predire()` retourne le montant. Avant cette date, chaque encaissement
  était vu comme une dépense.
- **Sens** : une catégorie de charge n'est jamais proposée pour un
  encaissement, un produit jamais pour un décaissement
  (`ENCAISSEMENTS_SEULEMENT` / `DECAISSEMENTS_SEULEMENT`). Vaut pour les
  règles comme pour le modèle.
- **Abstention** : sous 0,5 de confiance, `non_categorise_a_verifier`
  (« pas de proposition automatique » à l'écran). L'imputation automatique
  reste à 0,90 (`workflow/synchro.py`).
- **Modèle v2** (`_AUDIT_DONNEES/entrainer_modele.py`) : étiquettes étendues
  au compte courant d'associé (1 302 exemples jusque-là jetés), pondération
  des classes en racine. Validation croisée en 5 plis par dossier : 78,9 %
  d'exactitude ; à 0,5, 72,6 % des lignes proposées, 91,1 % justes (v1 : 64 %
  proposées, 91,6 % justes). Le v1 reste à côté pour revenir en arrière.
- **Propositions apprises** (`appris.py`) : une opération semblable à une
  opération déjà tranchée par l'indiv, dans le même sens, reprend sa
  catégorie en proposition. Mesuré sur le jeu d'audit en simulant un indiv
  qui tranche dans l'ordre : 81 % des lignes couvertes, 92 % justes.
- **Proposition à la lecture** (`api/routes.py`, `_avec_propositions`) : pour chaque
  opération à trancher, d'abord la proposition apprise, sinon les règles et
  le modèle en vigueur (`categoriser_lot`, un seul appel au modèle). Un
  nouveau modèle vaut donc tout de suite pour les opérations en attente. La
  proposition d'origine, figée à la synchro, reste en base comme trace
  (`etage_origine` des décisions).
- **Calibration** (`ml_fallback.Calibration`, fichier
  `<modèle>.calibration.json` écrit par `entrainer_modele.py`) : confiance
  calibrée, seuil de proposition, et seuil d'imputation propre à chaque
  catégorie, porté par la proposition (`ProposedEntry.seuil_imputation`)
  jusqu'à `workflow/synchro.choisir_compte`. Une catégorie non admise porte
  `inf` : jamais imputée seule. Chiffres : doc 05 §3.
- **Réentraînement sur les décisions** : `entrainer_modele.py --decisions`
  ajoute chaque décision humaine (hors dossiers `DEMO_`) comme exemple, lue en
  base, jamais écrite dans un fichier ; chaque dossier reste un groupe de la
  validation croisée.

## Catégories ajoutées le 2026-09-27

| Catégorie | Compte | Origine |
|---|---|---|
| `compte_courant_associe` | 455, 108 en EI (matrice des statuts) | modèle + règle générique |
| `virement_interne` | 580 | règle générique |
| `salaires_personnel` | 421 (le bulletin, 641/645/431, n'est pas produit) | décision de l'indiv |

Les règles ajoutées sont en confiance basse : elles proposent, l'indiv
tranche. `compte_courant_associe` n'a pas de compte dans le pack : même à
haute confiance, il reste à trancher, parce que son compte dépend du statut.

## Ordre des étages (AXE-826, 2026-11-05)

0. **Virements internes** (`virements_internes.py`) : deux jambes de montants
   opposés, à un jour près, sur deux comptes bancaires du dossier → 580,
   imputées sans question. Avant les règles : un virement « carburant » entre
   deux enveloppes n'est pas un plein.
1. **Règles** du pack ; celles qui décrivent un paiement à un commerçant
   (`CATEGORIES_DE_PAIEMENT`) ne s'appliquent pas à un virement
   (`type_operation == "transfer"`).
2. **Modèle** ML, qui s'abstient sous son seuil.
3. **Catégorie de la banque** (Bridge, `packs_vtc/categories_bridge.csv`) si
   le modèle s'abstient : `Etage.BANQUE`, confiance 0,5, une proposition
   jamais imputée.

La mémoire du pipeline est indexée par (libellé, montant, type d'opération,
catégorie de la banque) ; l'appariement se fait sur le lot, hors mémoire.
Mesure du 2026-11-05, sans modèle ML : MK DRIVING 18 % → 56 % classées seules,
B'CARS 6 % → 44 %.

## Statuts

- **Au 2026-11-05** : étages 1 et 2 (règles, modèle v2 calibré avec
  abstention) et propositions apprises des décisions (`appris.py`). La
  revue humaine existe : « À traiter » côté chauffeur (une carte à la fois,
  « Annuler », correction depuis Mouvements) et mode expert côté
  gestionnaire. Le pipeline garde son résultat par (libellé, montant),
  borné à 50 000 entrées, en mémoire de l'instance (AXE-565).
- **Étage 3 (LLM)** : la porte existe dans `pseudonymize/` (prompt
  pseudonymisé obligatoire, LLM interrogé seulement sous le seuil ML,
  jamais d'imputation par le LLM seul), mais aucun fournisseur n'est
  branché et `categorize` ne l'appelle pas encore.
- **V1 (doc 12, phase 2)** : pipeline complet à 4 étages, boucle de feedback
  continue (doc 07 §5).

## Doc de référence

[doc 05](../../../docs/05-pipeline-categorisation.md) (pipeline complet),
[doc 07](../../../docs/07-ml-donnees-entrainement.md) (ML, données, MLOps),
[doc 17 §3, §4bis](../../../docs/17-plan-demo-backend.md).
