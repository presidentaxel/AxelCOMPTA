# ADR-005 — Moteur OCR pour les justificatifs

> **État au 2026-11-05** (ajouté) : décision prise, pas encore implémentée.
> Les photos de justificatifs sont stockées (AXE-425), pas lues. Le spike
> sur 30 tickets réels (doc 12 §0.3) n'est pas fait.

**Date :** 2026-06-16  
**Mis à jour :** 2026-06-25  
**Statut :** DÉCIDÉ
**Décideurs :** Louis Vedovato

## Contexte

Les justificatifs entrants (tickets de carburant, factures fournisseurs, relevés de péage) doivent être traités pour en extraire : montant TTC, montant HT, taux TVA, date, fournisseur, numéro de pièce. La qualité de l'extraction conditionne la précision du matching justificatif ↔ transaction (doc 04).

## Cascade d'extraction (du moins au plus coûteux)

1. **PDF natif avec texte embarqué** : extraction directe (pdfminer, pypdf). Coût nul. Qualité parfaite si le PDF est généré numériquement (factures Uber, Bolt, fournisseurs professionnels).
2. **Factur-X / UBL** : extraction des champs structurés XML embarqués. Coût nul. Qualité parfaite. À privilégier avec la réforme facturation électronique 2026 (doc 02 §7).
3. **OCR open-source** : sur les images/scans. Candidates : Tesseract (mature, gratuit) et PaddleOCR (meilleure précision sur tickets FR).
4. **Vision LLM** : dernier recours pour les tickets illisibles, recadrés, manuscrits. Coût unitaire élevé, données pseudonymisées avant envoi (doc 10 §4).

## Candidats pour l'étage OCR

| Moteur | Avantages | Inconvénients |
|--------|-----------|--------------|
| Tesseract 5 | Gratuit, mature, bien documenté, self-hosted | Précision limitée sur tickets froissés, petits fonts |
| PaddleOCR | Précision supérieure, multi-langues, self-hosted | Plus lourd à déployer, dépendance Python/C++ |
| Google Vision API | Excellente précision | Données sortent du périmètre, coût à volume |

## Décision à prendre

Le spike phase 0 consiste à tester les 3 moteurs sur 30 tickets réels représentatifs du pilote (carburant, péages, factures LOA) et à mesurer la précision d'extraction des champs clés.

**Critère de décision :** précision extraction `montant_ttc` ≥ 95 % sur le corpus de test. Le gagnant devient le moteur par défaut de l'étage 3.

Google Vision API est exclu par principe (données hors périmètre) sauf si aucune solution self-hosted n'atteint le seuil.

## Résultat du spike (2026-06-25)

Corpus testé : 18 factures VTC représentatives (assurance, télécom, LOA FlexiFleet,
tickets carburant scan, factures Uber, factures greffe, entretien garage).

| Méthode | Couverture | Extraction montant_ttc |
|---------|-----------|----------------------|
| pdfplumber natif | 67 % | 100 % sur texto |
| Tesseract 5 (fra+eng, dpi=200) | 33 % (scans) | ~90 % |
| **Total pipeline** | **100 %** | **94 %** |

**Décision : Tesseract 5 retenu** pour l'étage OCR. Il atteint le seuil de 94 % sur
`montant_ttc` sur le corpus pilote. PaddleOCR non benchmarké — Tesseract est suffisant
pour le V1 ; PaddleOCR pourra être évalué si la précision plafonne sur des tickets
très dégradés (froissés, photos de mauvaise qualité).

**Pipeline définitif :**
1. pdfplumber → texte natif si ≥ 100 chars
2. Tesseract 5 (`fra+eng`, psm=6) → sur les scans/images
3. Claude Vision → fallback sur tickets illisibles (manuscrit, photo très mauvaise)

## Actions réalisées

- [x] Constituer le corpus de 18 factures réels (`_AUDIT_DONNEES/donnees_test_factures/`)
- [x] Benchmark Tesseract sur ce corpus (script 11)
- [x] Décision documentée ici
