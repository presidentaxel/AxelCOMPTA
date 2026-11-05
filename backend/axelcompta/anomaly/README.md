# anomaly/

Détection d'abus / anomalies sur les transactions catégorisées, scoring,
alertes.

**Dépendances :** `core`, `categorize` (lit les `ProposedEntry`).

## Contenu prévu (V1)

Voir [doc 05 §6](../../../docs/05-pipeline-categorisation.md#6-détection-danomalies-et-dabus-module-anomaly)
pour le détail — scoring paramétré par pack métier (pas de règle en dur
transverse).

## Fichiers

- `profil.py` : profil par dossier et par catégorie, en sommes entières.
- `detecteurs.py` : détecteurs V1 — catégorie personnelle, enseigne
  ambiguë, écart au profil (3σ), doublon de pièce, double plein. Aucun
  libellé juridique dans les alertes.
- `instruction.py` : cycle de vie d'une alerte (ouverte → en instruction →
  justifiée avec commentaire, usage personnel, ou faux positif).
- `service.py`, `models.py` : point d'entrée et types.

## Statuts

- **Fait le 2026-10-24 (AXE-437, PR #50)** : profils, détecteurs V1, écran
  gestionnaire `/anomalies/{dossier}`, accessible depuis le mode expert
  (AXE-700). Un rôle Lecture consulte sans qualifier.
- **Limite** : les qualifications sont en mémoire de process
  (`demo_api.py`). Elles disparaissent au redémarrage de l'API. À
  persister en base avant le pilote.
- **V1 (doc 12, phase 2.5)** : templates comptables de résolution (455/108
  selon le statut), jeu d'évaluation (rappel et précision), paramètres par
  pack.

## Doc de référence

[doc 05 §6](../../../docs/05-pipeline-categorisation.md#6-détection-danomalies-et-dabus-module-anomaly).
