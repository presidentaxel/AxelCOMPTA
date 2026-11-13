# closing/

Clôture d'exercice, états financiers (bilan, compte de résultat), modèle
pivot de liasse (`LiassePivot`) avant rendu par `filings/`.

**Dépendances :** `core`, `ledger`.

## Fichiers

- `models.py` — `LiassePivot`.
- `service.py` — `ClosingService`, façade abstraite.
- `bilan_simplifie.py` — `ClotureSimplifieeService` (**fait, semaine 3**) :
  balance → compte de résultat (produits/charges via `core.pcg`) → bilan
  (trésorerie, résultat, TVA à payer) → `LiassePivot` avec une case-clé 2065
  (résultat fiscal, aucune réintégration — hors scope démo). Avec
  `ParametresCloture`, délègue à la clôture fiscale ci-dessous.
- `cloture_fiscale.py` (2026-09-23, doc 17 §15) : clôture IS au régime
  simplifié. Écritures d'inventaire (`ecritures_cloture.py` : liquidation
  TVA, IS 695/444), IS (`impot_societes.py` : 15 % jusqu'à 42 500 €
  proratisé, 25 % au-delà), tableaux 2033-A/B (`liasse_2033.py`) et
  2033-C/D/E (`liasse_2033_annexes.py`), le tout dans une `LiassePivot`
  indexée par code officiel (`2033B.310`...). Correspondance comptes →
  rubriques : `rubriques_2033.py`, d'après la notice 2033-NOT-SD, sans
  relecture d'expert-comptable (décision démo). Les écritures d'inventaire
  sont toujours recalculées depuis le grand livre privé d'elles-mêmes
  (`hors_inventaire`) : passées en base à la clôture, elles ne comptent
  pas double et la liasse de l'exercice clos ne bouge pas.
- `affectation.py` + `fiscalite_dividendes.toml` (**2026-09-26**) :
  affectation du résultat. Réserve légale, distribuable, trésorerie
  disponible, scénarios de dividendes chiffrés au PFU de l'année de
  versement, écriture qui solde le résultat. Appelée par
  `axelcompta/affectations.py`.
- `dividendes.py` (**2026-09-27**) : retenues à la source sur les
  dividendes versés (457 vers 4423) et échéance de la 2777.
- `paie.py` (**2026-09-27**) : bulletin du président assimilé salarié,
  passé tel quel (641, 645, 431, 4421, 421), sans calcul de paie.
- `ouverture.py` (**2026-09-26**) : écriture d'à-nouveaux (journal AN) à
  l'ouverture de l'exercice suivant, comptes de bilan repris, résultat en
  120 ou 129. Appelée par `axelcompta/exercices.py`.

## Statuts

- **Au 2026-11-05** : clôture fiscale (TVA, IS, réintégrations, amendes),
  liasse 2033 et 2031, réel normal (2050 à 2058-B en totaux, sans PDF),
  CA3 annuelle (`ca3.py`), contrôles inter-cases (`controles_tdfc.py`),
  CCA/FNP saisies par le chauffeur (`provisions.py`), paie du président
  (`paie.py`), affectation du résultat et dividendes, à-nouveaux d'un
  exercice clos dans AxeLCompta (`ouverture.py`). Le bilan simplifié
  s'équilibre avec le capital et les immobilisations (AXE-421).
- **Fait depuis le 2026-11-05** : provisions qui ne s'écrasent plus après
  une lecture ratée (AXE-685), CA3 par période (AXE-805, ci-dessous),
  clôture et liasse qui attendent la configuration confirmée par le
  chauffeur (AXE-730), refus de clôture en erreur métier `PassageRefuse`
  (409, AXE-853).
- **Fait du 2026-11-11 au 2026-11-13** : bilan d'ouverture repris d'un
  FEC et déficits antérieurs (AXE-804, ci-dessous), identité de la société
  saisie par le dirigeant (AXE-846, dans `tenants/`), immobilisations et
  amortissement (`immobilisations.py`, AXE-802), LOA (`loa.py`, AXE-803 :
  premier loyer étalé en 486, engagement hors bilan, levée d'option en
  2182). Plafond de l'art. 39-4 non appliqué au transport de personnes, à
  valider (AXE-815).
- **Manque pour la V1** : saisie guidée d'un bilan d'ouverture sans FEC,
  reprise des immobilisations à l'ouverture, rapprochement bancaire ligne à
  ligne, lignes de détail des annexes 2054 à 2059 (AXE-484).

## Doc de référence

[doc 06 §5](../../../docs/06-moteur-comptable.md#5-clôture-dexercice-closing).

## Bilan d'ouverture repris d'un FEC (AXE-804)

`ouverture_fec.py` (pur) lit le FEC de l'outil précédent, tolérant aux
variantes réelles (tabulation ou `|`, CR+LF ou LF, UTF-8 ou Windows-1252,
Debit/Credit ou Montant/Sens, numéros par journal), le contrôle, et en tire
l'écriture d'à-nouveaux avec `ecriture_a_nouveaux` (le même calcul qu'un
passage d'exercice). Garde-fous : nom `SIRENFECAAAAMMJJ`, SIREN du dossier,
clôture la veille de l'ouverture, équilibre, dates dans l'exercice et pas de
validation future, comptes inconnus à faire correspondre ; alertes sans
capital, sans banque, et solde de banque à comparer au relevé. Attestation
de la personne qui importe (dirigeant, ou expert-comptable habilité avec un
motif), empreinte du fichier, une seule reprise par dossier
(`ouverture_depot.py`, table `ouvertures_importees`, tout ou rien avec
l'à-nouveaux et les déficits). `Dossier.deficits_anterieurs_euros` alimente
la liasse et l'IS, et passe à l'exercice suivant (2033-D ligne 870).

## TVA en cours d'année (AXE-805)

`tva_periodique.py` (pur) : périodes mensuelles ou trimestrielles de
l'exercice, échéance (jour réglé par le dirigeant : `dossiers.tva_periodicite`,
`tva_jour_echeance`, migration `d4a8f2c6e195`), CA3 de chaque période
(collectée dont autoliquidée, déductible hors 44567, crédit reporté de la
période précédente) et écriture de liquidation `{dossier}:tva-periode-{clé}`
vers 44551 ou 44567. La CA3 annuelle de la liasse relit les mouvements hors
ces liquidations : elle reprend la somme des périodes. `tva_rappels.py` :
rappels J-7 et J-2 dans la cloche. La déclaration est prouvée dans
`documents_signes` (`tva_ca3_{clé}`).
