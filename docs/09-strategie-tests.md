# 09 — Stratégie de tests

> **État au 2026-11-13** (ajouté) : en plus des tests unitaires, de
> propriétés et des golden tests de liasse, le frontend a des tests de
> bout en bout Playwright (`frontend/e2e/`, dont la répétition de la démo,
> AXE-431). Au 13/11 : environ 1 390 tests rapides et 145 d'intégration
> (Postgres local, rôle web et RLS compris). Tests de contrat hors CI, à
> lancer avec un jeton : Rollee sandbox (`pytest -m rollee`). Les clients
> INSEE, RNE, Rollee et Anthropic sont testés sur des réponses construites
> d'après leur documentation. Mesure des objectifs V1 :
> `scripts/mesurer_objectifs.py` (AXE-816) ; le jeu de test gelé n'existe
> pas encore (AXE-902, AXE-423).

> Statut : brouillon à valider — Dernière mise à jour : 2026-06-12

## 1. Doctrine

Un logiciel comptable a une chance que la plupart des logiciels n'ont pas : **la
vérité est calculable**. Une balance s'équilibre ou pas ; un FEC est conforme ou
pas ; un plan d'amortissement se recalcule à la main. La stratégie exploite ça à
fond : beaucoup d'**invariants** et de **golden tests** vérifiables, plutôt que des
mocks qui testent l'implémentation.

Répartition visée :

```text
        ▲  E2E (peu, les parcours critiques)         ~5 %
       ▲▲  Intégration (DB réelle, frontières)        ~25 %
     ▲▲▲▲  Unitaires + propriétés + golden (le cœur)  ~70 %
```

## 2. Tests unitaires et de propriétés (le socle)

### 2.1 `ledger` — objectif 100 % de couverture, sans excuse

- Tests exemples classiques sur chaque template d'écriture (doc 06 §3) : cas
  chiffrés, calculés à la main, vérifiés par votre comptable de référence.
- **Tests de propriétés (Hypothesis)** — les invariants I1-I8 :
  - ∀ écriture générée par n'importe quel template avec n'importe quels montants
    valides : Σ débits = Σ crédits.
  - ∀ plan d'amortissement : Σ dotations = base amortissable, au centime, quelle
    que soit la durée et la date de mise en service (les arrondis de la dernière
    dotation sont LE nid à bugs).
  - ∀ séquence d'écritures + contre-passations : la balance reste équilibrée.
  - ∀ montant : parse(format(m)) == m (aller-retour centimes ↔ affichage).
- Tests aux limites : exercices à cheval sur année bissextile, écriture au 31/12,
  immobilisation mise en service le 29 février, montants à 1 centime, prorata
  temporis premier/dernier mois.

### 2.2 `ingestion` — la jungle des formats

- Corpus de fixtures par format/banque (fichiers réels anonymisés) : chaque bug
  de parsing rencontré en prod **devient une fixture** avant d'être corrigé
  (non-régression perpétuelle).
- Propriétés : parsing des montants FR/EN, dates, encodages — sur entrées générées.
- Idempotence : tout import rejoué = zéro doublon (test systématique).
- Fichiers hostiles : tronqués, colonnes manquantes, 100 000 lignes, cellule
  piégée (`=HYPERLINK(...)` — injection de formule), ZIP bomb sur les uploads.

### 2.3 `categorize` — règles et pipeline

- **Chaque règle embarque ses cas de test** (doc 05 §2.2), exécutés en CI ; une
  règle sans test ne s'active pas.
- Tests de collision : détection automatique des paires de règles qui matchent les
  mêmes libellés du corpus avec des actions différentes.
- Pipeline : matrice de scénarios (règle match / ML confiant / ML hésitant / LLM
  d'accord / LLM en désaccord / LLM en panne / tout en panne) → le comportement
  attendu de chaque case est spécifié et testé. Le LLM est mocké ici (déterminisme).

## 3. Golden tests (non-régression sur les sorties réglementaires)

Des **dossiers de référence complets** (3 à 5 dossiers synthétiques : une SASU
avec achat de véhicule, une EURL en LOA, une EURL avec option IR, dont un dossier
qui traverse la fin d'option IR : exercice N en IR → N+1 en IS — un par colonne
opérationnelle de la matrice doc 06 §7) traversent tout
le système, et leurs sorties sont figées :

| Sortie | Vérification |
|--------|--------------|
| FEC | Comparaison octet à octet avec le FEC de référence + passage dans « Test Compta Demat » (outil DGFiP) en CI. |
| Balance, grand livre | Comparaison structurée (CSV trié). |
| Liasse pivot | Comparaison case par case (JSON), avec les contrôles de cohérence inter-cases du cahier des charges TDFC. |
| PDF | Comparaison du texte extrait (pas des pixels), + revue visuelle à chaque changement de template. |

Tout écart = échec CI. Un changement légitime (évolution fiscale) exige une mise à
jour **explicite et revue** du golden, avec la source réglementaire en message de
commit.

## 4. Tests d'intégration

- **Postgres réel éphémère** (testcontainers) — pas de SQLite « pour aller vite » :
  les transactions, contraintes, RLS et verrous sont précisément ce qu'on teste.
- Migrations : chaque PR rejoue toutes les migrations sur base vide + un test
  upgrade/downgrade.
- Concurrence : deux validations simultanées sur le même dossier → numérotation
  séquentielle sans trou ni doublon (test avec vraies transactions parallèles).
- Digifactory (canal actif — doc 16) : mock du serveur HTTP (respx/VCR), développé
  contre des fixtures en attendant un token fonctionnel (doc 16 §7), remplacées par
  des payloads réels capturés dès le déblocage ; scénarios de `since` incrémental,
  transaction mise à jour rétroactivement, transaction supprimée, connexion en
  échec, réponse vide (doc 16 §9.7).
- **Tests d'isolation multi-tenant** : une suite dédiée tente systématiquement
  d'accéder aux données d'un tenant B avec une session du tenant A, sur chaque
  endpoint (générée depuis l'OpenAPI). Zéro fuite tolérée.

## 5. Tests E2E (Playwright)

Les parcours critiques uniquement, sur staging avec données synthétiques :

1. Import d'un fichier CSV → prévisualisation → confirmation → transactions visibles.
2. File de revue : valider, corriger, créer une règle depuis une correction.
3. Instruction d'une alerte d'anomalie de bout en bout.
4. Clôture d'un exercice du dossier de référence → liasse générée.
5. Circuit signature : génération du lien, ouverture sans compte, relecture,
   signature, document final archivé.

## 6. Tests spécifiques ML et OCR

Voir doc 07 §4 et §7. S'ajoutent à la CI applicative :

- Test de chargement du modèle champion au démarrage (smoke).
- Test de contrat : le modèle répond sur la taxonomie courante (pas une catégorie
  retirée), avec des probabilités qui somment à 1.
- Golden OCR : N documents de référence → extraction attendue.
- Tests du pseudonymiseur (doc 10 §4) : sur un corpus contenant noms/IBAN/téléphones
  connus, **zéro fuite** dans la sortie — c'est un test de sécurité, bloquant.

## 7. Tests de charge et de robustesse (avant mise en prod)

- Charge réaliste : 200 dossiers × 250 transactions/mois ≈ 50 000 transactions/mois
  — c'est *petit* ; le test vise les pics : reprise d'historique 10 ans d'un coup
  (~3 M de lignes), clôtures groupées au 31/12, import de 500 justificatifs.
- Chaos léger : couper le LLM, couper Digifactory, tuer un worker en plein batch →
  vérifier reprise propre et zéro corruption (les jobs sont idempotents, on le
  prouve).
- **Restauration de sauvegarde : testée trimestriellement, chronométrée,
  documentée.** Une sauvegarde non testée n'existe pas.

## 8. Qui valide la comptabilité elle-même ?

Les tests prouvent que le code fait ce qu'on a spécifié — pas que la spécification
comptable est juste. Dispositif complémentaire :

- **Relecture des templates d'écritures et des dossiers de référence par un
  expert-comptable** (prestation ponctuelle, quelques jours) avant la V1, puis à
  chaque millésime fiscal. Budget à prévoir, non négociable.
- **Ajouté 2026-09-11 (doc 06 §5bis)** : le délai de battement avant
  clôture (combien de temps attendre après le 31/12 pour considérer les
  données bancaires stables) et la politique de provisionnement CCA/FNP
  pour le résiduel non arrivé sont des décisions comptables, pas des choix
  d'ingénierie — à faire trancher par l'expert-comptable au même moment
  que la relecture des templates, pas devinées.
- Cadrages croisés permanents en prod : TVA déclarée vs comptabilisée, solde 512 vs
  relevés, totaux liasse vs balance — des jobs qui vérifient, pas des humains.

## 9. Métriques de qualité suivies en continu

| Métrique | Seuil |
|----------|-------|
| Couverture `ledger/closing/filings` | ≥ 95 % (bloquant CI) |
| Couverture globale backend | ≥ 85 % (bloquant CI) |
| Durée suite rapide (unit + propriétés) | < 5 min (sinon on optimise la suite) |
| Flaky tests | 0 toléré — un test instable est réparé ou supprimé le jour même |
| Bugs prod sur le cœur comptable | Chaque bug = post-mortem court + fixture de non-régression |
