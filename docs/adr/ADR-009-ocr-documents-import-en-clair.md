# ADR-009 — OCR des documents d'import : envoi en clair à Anthropic, encadré

**Date :** 2026-11-19
**Statut :** décidé (exception temporaire, à réduire)
**Décideurs :** Louis Vedovato
**Ticket :** AXE-994

## Contexte

L'OCR des fiches d'import (AXE-943, module `backend/axelcompta/ocr/`, en
production depuis le 18/11 au soir) envoie à Claude (Anthropic) le fichier
déposé **tel quel** : PDF en bloc `document`, image en bloc `image`. Partent
donc, en clair, les noms des dirigeants et des associés, les adresses, les
SIREN, les montants, les IBAN et les libellés des relevés bancaires.

C'était contraire :

- à l'invariant n° 5 des règles du projet (« Avant tout appel LLM :
  pseudonymisation obligatoire ») ;
- au doc 10 et à l'ADR-005 (étage Vision LLM « données pseudonymisées avant
  envoi ») ;
- à la politique de confidentialité publiée, qui ne citait Anthropic que
  pour des libellés pseudonymisés.

`pseudonymize/` ne travaille que sur du texte. Les documents de reprise sont
des PDF et des scans, et une partie des contrôles a besoin des données en
clair : SIREN égal à celui de la fiche, noms des associés, clé de l'IBAN.

## Options étudiées

| Piste | Ce que ça veut dire | Limite |
|---|---|---|
| A. Texte d'abord, pseudonymisé | Pour un PDF texte, extraire le texte chez nous, le pseudonymiser, n'envoyer que lui | Scans et photos non couverts ; contrôles à refaire de notre côté |
| B. Masquer l'image | OCR local pour repérer les zones sensibles, les noircir avant l'envoi | Plus lourd ; un masquage peut rater une zone |
| C. Tout en local | Moteur open-source (Tesseract, PaddleOCR) | Lecture nettement moins bonne sur liasses et relevés scannés |
| D. Acter l'exception | Garder l'envoi en clair, l'encadrer (contrat, textes, AIPD) | Juridique et contractuel ; les documents restent des données personnelles |

## Décision

1. **L'OCR continue de tourner** (`AXELCOMPTA_OCR_ACTIF=1`), avec son
   plafond mensuel (`AXELCOMPTA_OCR_PLAFOND_MOIS_USD`, 4 $ en production).
2. **Option D, tout de suite** : l'exception est écrite ici, dans le doc 10,
   dans l'invariant n° 5 et dans la politique de confidentialité. Elle est
   limitée à l'OCR des documents déposés sur une fiche d'import. **L'étage
   LLM de catégorisation reste pseudonymisé**, sans exception.
3. **Ensuite, pas à pas vers une solution plus propre** :
   - réduire ce qui part : n'envoyer que les pages utiles (AXE-999 pour les
     grands livres) ;
   - piste A pour les PDF texte : texte extrait et pseudonymisé chez nous,
     contrôles en clair refaits de notre côté ;
   - piste B ou C pour les scans, quand le volume le justifie.

## Ce qui encadre l'exception

- **Seulement l'OCR des fiches d'import** : un document déposé par le
  gestionnaire pour la reprise d'une entreprise. Ni les opérations
  bancaires courantes, ni les justificatifs du quotidien.
- **Ce qui est lu n'est jamais appliqué sans contrôle** : chaque lecture
  passe les contrôles de sa catégorie (arithmétique, recoupement avec le FEC
  et la fiche). Sinon, un humain tranche. Un champ de la fiche n'est rempli
  que s'il est vide.
- **Interrupteur et plafond** : `AXELCOMPTA_OCR_ACTIF` vide coupe tout
  envoi ; au-delà du plafond du mois, plus rien ne part.
- **Clé dédiée** : `ANTHROPIC_API_KEY` et `ANTHROPIC_WORKSPACE_ID` dans
  l'environnement du serveur, jamais dans le dépôt.

## Reste à faire (hors code)

- [ ] Vérifier et écrire les conditions d'Anthropic pour l'API : durée de
      conservation des requêtes, usage pour l'entraînement, région de
      traitement, DPA et clauses contractuelles types. Ne rien supposer :
      les blancs restent `[À COMPLÉTER]` tant que ce n'est pas lu dans le
      contrat signé.
- [ ] Informer les clients existants de ce nouvel usage d'un sous-traitant
      déjà listé (annexe art. 28, point 4).
- [ ] Analyse d'impact (AIPD) : ajouter ce traitement à celle du doc 02 §8.
- [ ] Relecture par le juriste (AXE-813) de la confidentialité mise à jour.

## Conséquences

- La politique de confidentialité dit ce qui part réellement chez Anthropic.
  Le test `frontend/lib/juridique.test.ts` vérifie qu'elle continue de le dire.
- Toute nouvelle catégorie OCR, ou tout nouvel usage d'un LLM sur un
  document, doit être couvert par cet ADR ou en appeler un nouveau.
- Quand la piste A sera en place pour les PDF texte, cet ADR passera à
  « remplacé en partie », et la confidentialité sera remise à jour dans la
  même PR.
