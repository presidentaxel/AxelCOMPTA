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
- **Manque pour la V1** : dotations aux amortissements (AXE-802), LOA
  (AXE-803), bilan d'ouverture d'une société existante (AXE-804), CA3 par
  période (AXE-805), rapprochement bancaire, lignes de détail des annexes
  2054 à 2059 (AXE-484). Bug ouvert : provisions écrasables (AXE-685).

## Doc de référence

[doc 06 §5](../../../docs/06-moteur-comptable.md#5-clôture-dexercice-closing).
