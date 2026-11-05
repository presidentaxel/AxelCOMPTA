# documents/

Justificatifs : stockage, OCR, Factur-X, matching avec les transactions
bancaires.

**Dépendances :** `core`, `tenants`.

## Contenu prévu (V1)

- Extraction native PDF → OCR open-source (Tesseract/PaddleOCR) → Vision LLM
  en fallback (hybride, doc 04 §4, arbitré par ADR-005).
- Parsing Factur-X.
- Matching justificatif ↔ transaction bancaire.
- Stockage S3-compatible avec versioning + verrouillage WORM (archivage
  légal).

## Statuts

- **Fait le 2026-10-24 (AXE-425, PR #51)** : stockage des photos de
  justificatifs. Une photo est rangée par tenant et dossier (`fichier.py`),
  avec empreinte et 8 Mo max ; un identifiant qui sortirait du dossier est
  refusé. Les lignes vont dans la table `justificatifs` (`postgres.py`,
  `orm.py`) sous le rôle web, avec RLS. `memoire.py` sert aux tests. Le
  chauffeur attache une photo à une seule dépense, choisie avant l'envoi
  (AXE-483).
- **Pas fait** : lecture de la photo (OCR), Factur-X, matching automatique,
  stockage WORM. Le spike OCR (30 tickets réels, Tesseract vs PaddleOCR vs
  Vision LLM) reste le préalable.

## Doc de référence

[doc 04 §4](../../../docs/04-ingestion-donnees.md#4-justificatifs--ocr-vision-factur-x),
[ADR-005](../../../docs/adr/ADR-005-moteur-ocr.md),
[doc 07 §7](../../../docs/07-ml-donnees-entrainement.md#7-ocrvision--évaluation-spécifique).
