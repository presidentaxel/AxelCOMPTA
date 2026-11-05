# filings/

Renderers : FEC, PDF de liasse, EDI-TDFC, dossier INPI.

**Dépendances :** `core`, `closing`.

## Fichiers

- `renderer.py` — `FilingRenderer`, façade abstraite.
- `liasse_simplifiee.py` — `PdfLiasseSimplifieeRenderer` (**fait, semaine 3**) :
  compte de résultat + bilan + case-clé 2065, présentation lisible (reportlab).
  **Pas de conformité CERFA/DGFiP, pas d'EDI, pas d'INPI** — c'est écrit
  noir sur blanc dans le PDF lui-même pour qu'on ne s'y trompe jamais.
- `overlay_cerfa.py` : écriture par-dessus un formulaire officiel sans
  AcroForm (ADR-006) ; montants alignés à droite, caractères centrés dans
  les cases, croix.
- `cerfa/2065-sd_2026.pdf` + `cerfa_2065.py` : `PdfCerfa2065Renderer`,
  2065-SD et 2065-bis-SD officiels. Avec une clôture fiscale (2026-09-23) :
  exercice, régime simplifié, identité complète (dénomination, siège,
  SIRET, courriel), activité, bénéfice ventilé 15 % / taux normal ou
  déficit, comptabilité informatisée, bloc signataire, cadre J. Sans
  identité (dossier historique pseudonymisé), le cadre A reste blanc : on
  n'invente pas d'identité réelle.
- `cerfa/2033-sd_2026.pdf` + `cerfa/cases_2033-sd_2026.json` +
  `cerfa_2033.py` : `PdfLiasse2033Renderer`, les 7 tableaux 2033-A à G
  officiels. Coordonnées des cases extraites du PDF par
  `scripts/extraire_cases_cerfa.py` (ADR-006, §Extension au 2033).
- `cerfa/2031-sd_2026.pdf` + `cerfa_2031.py` (**2026-09-26**) :
  `PdfCerfa2031Renderer`, 2031-SD et 2031-bis-SD officiels, pour la colonne
  à l'IR de la matrice des statuts. Exercice, régime simplifié, identité,
  activité, cadre C (bénéfice 370 ou déficit 372 de la 2033-B, total,
  bénéfice imposable), comptabilité informatisée, déclarant, cadre E
  (associés, gérant, « B », quote-part au prorata des titres) et cadre H.
  Route `/dossiers/{id}/cerfa-2031.pdf` (409 pour un dossier à l'IS, comme
  la 2065 l'est pour un dossier à l'IR).
- `liasse_fiscale.py` : `PdfLiasseFiscaleRenderer`, déclaration de résultat
  (2065 + 2065-bis à l'IS, 2031 + 2031-bis à l'IR, selon
  `LiassePivot.soumis_is`) + 2033-A à G en un PDF, sans les pages de
  notice. Route `/dossiers/{id}/liasse-fiscale.pdf`.

Aucun de ces PDF n'est une télédéclaration : le dépôt légal est EDI/EFI
(statut Partenaire EDI, doc 02).
- `fec.py` : `exporter_fec()`, conforme au texte de l'article A.47 A-1
  depuis le 2026-09-23 (virgule décimale, `EcritureNum` continu, `CompteLib`
  toujours renseigné, CR+LF, nom `<SIREN>FEC<AAAAMMJJ>.txt`). **Le format
  légal exigé en cas de contrôle fiscal.** Pas encore passé dans « Test
  Compta Demat » (outil DGFiP, Windows).
- `export_comptable.py` — `exporter_grand_livre()`/`exporter_balance()`
  (**fait, 2026-09-05**) : CSV, doc 06 §6 (« pour l'expert-comptable du
  client »). Réutilisent les mêmes libellés de compte que le FEC.

## Statuts

- **Démo, 2026-09-23 (doc 17 §15)** : liasse fiscale complète 2065 + 2033
  sur les formulaires officiels, FEC conforme au texte.
- **Démo (doc 17 semaine 3, fait)** : `PdfLiasseSimplifieeRenderer` produit
  un PDF qui présente un compte de résultat et un bilan simplifiés (plus le
  dump brut de comptes de la semaine 0/2, remplacé). `PdfCerfa2065Renderer`
  ajoute la fidélité visuelle au vrai formulaire pour la case résultat.
  `fec.py`/`export_comptable.py` ajoutent le détail (journal, grand livre,
  balance) qui manquait derrière les chiffres de la liasse.
- **2026-10-14/25** : le FEC passe un validateur A.47 A-1 (ce n'est pas
  Test Compta Demat) et reste un fichier texte, affiché « FEC » (AXE-422,
  AXE-558). Une case à zéro reste vide sur les formulaires et les exports,
  le FEC garde `0,00` (AXE-557). La liasse et la signature greffe sont
  refusées (409) tant qu'une opération est au compte d'attente (AXE-687).
- **V1 (doc 12, phase 3)** : conformité complète sur toute la liasse
  (2050-2059G/2033A-G, pas seulement le récapitulatif 2065), testée via
  « Test Compta Demat » (spike FEC, doc 12 §0.3), EDI-TDFC (doc 02 —
  stratégie Partenaire EDI en 3 temps, la seule vraie voie de dépôt légal),
  dépôt INPI.

## Doc de référence

[doc 06 §6](../../../docs/06-moteur-comptable.md#6-renderers-filings),
[doc 02](../../../docs/02-cadre-reglementaire.md) (cadre réglementaire FEC/EDI/INPI),
[doc 17 §3, §6](../../../docs/17-plan-demo-backend.md).
