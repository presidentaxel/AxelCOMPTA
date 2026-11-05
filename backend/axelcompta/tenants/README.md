# tenants/

Tenants (mode portefeuille ou mono), dossiers, et l'un des deux axes de
configuration : le **statut** (forme juridique, régime fiscal, régime TVA).
L'autre axe (le **pack métier**) vit dans [`packs/`](../packs/README.md).

Chaque dossier est indépendant et porte sa configuration complète en propre —
le tenant ne fournit que des valeurs de pré-remplissage à la création, jamais
d'héritage implicite (doc 03 §3bis, doc 06 §7).

**Dépendances :** `core`.

## Contenu prévu (V1)

- Modèles tenant + dossier, RLS (Row-Level Security Postgres) + middleware
  d'isolation, suite de tests d'isolation dédiée.
- Matrice de configuration statut × régime (doc 06 §7), en données
  versionnées : **faite le 2026-09-26** (`matrice_statuts.toml`), colonnes
  société à l'IS, à l'IR et EI au réel opérationnelles (2065 ou 2031).
  Reste la micro-entreprise (livre des recettes, pas de bilan).
- Option IR bornée (**faite le 2026-09-26**, `avenants.py`) : date de
  début, décompte des 5 exercices, alertes N-1/N,
  bascule IS tracée, changement de régime par avenant daté.

## Fichiers

- `sirene.py` (AXE-834) — configuration tirée de Sirene, pure : premier
  exercice à la date de création d'une société créée dans l'année, forme
  (SAS ou SARL marquées « à confirmer » : Sirene ne distingue plus
  l'associé unique depuis 2020), activité NAF. `Dossier.code_naf` et
  `Dossier.a_confirmer` (migration `d4a8c2e61f37`) ; le gestionnaire voit
  « … à confirmer par le dirigeant » dans Entreprises.

- `models.py` — domaine pur (`Tenant`, `Dossier`).
- `agregats.py` / `agregats_postgres.py` (**fait, AXE-566**) : les agrégats de
  la vue portefeuille (montants de la liasse, exercice, alerte de franchise)
  gardés par dossier dans `agregats_dossier`. Périmés par des triggers
  Postgres (migration `e7b3d9a15c42`), recalculés dossier par dossier avec un
  compare-and-set sur `version`. `VERSION_CALCUL` invalide tout. Voir
  `axelcompta/agregats_portefeuille.py` pour réchauffer et vérifier.
- `affectations.py` / `affectations_postgres.py` (**fait, 2026-09-26**) :
  décisions d'affectation du résultat, une par exercice clos, append-only
  (table `affectations_resultat`, verrou en base, journal d'audit).
- `exercices.py` / `exercices_postgres.py` (**fait, 2026-09-26**) :
  historique append-only des exercices clos (table `exercices_clos`, verrou
  en base), avec ce qui a changé à l'ouverture du suivant.
  `DossierRepository.ouvrir_exercice` est la seule mise à jour de
  configuration admise, à ce moment-là.
- `franchise_tva.py` + `seuils_franchise_tva.toml` (**fait, 2026-09-26**) :
  seuils de la franchise en base par millésime (BOFIP), état du dossier
  selon son chiffre d'affaires HT de l'année civile (sous le seuil,
  approche, seuil de base ou majoré dépassé), prorata la première année.
- `avenants.py` / `avenants_postgres.py` (**fait, 2026-09-26**) : avenants
  de régime datés, append-only (table `avenants_regime`, verrou en base).
  `regime_pour_exercice`, alertes de fin d'option IR, bascule vers l'IS
  programmée par `axelcompta.taches` au dernier exercice de l'option.
- `matrice_statuts.toml` + `statuts.py` (**fait, 2026-09-26**) : matrice
  statut × régime (doc 06 §7) en données versionnées. Chaque couple (forme,
  régime) mène à une colonne (`societe_is`, `societe_ir`, `ei_reel`,
  `micro`) qui dit l'impôt, les formulaires, le dépôt au greffe et le compte
  d'usage personnel. `configuration_de(dossier)` valide et type la
  configuration (erreurs toutes ensemble) ; les repositories l'appellent
  avant chaque écriture. Seule `societe_is` est opérationnelle de bout en
  bout ; les autres se créent et se lisent, leurs formulaires restent à
  faire. Ajouter un statut = ajouter des données, pas une migration.
  La matrice porte aussi le compte de la rémunération du dirigeant par
  forme (641, 644, 108 ; SARL à préciser), lu par
  `ConfigurationDossier.comptes_categories_statut`.
- `orm.py` — mapping SQLAlchemy Core (**étendu le 2026-09-21**) : tables
  `tenants` et `dossiers` (nom, régime TVA recettes, début d'exercice,
  plateformes, mode d'accès bancaire, `contact_nr` Digifactory unique). Un
  seul schéma, aucune colonne RLS.
- `repository.py` / `memory.py` / `postgres.py` (**fait, 2026-09-21**) :
  `DossierRepository`. `lister_par_tenant` est **le** point d'isolation entre
  portefeuilles ; `par_contact_nr` est la table de correspondance
  Digifactory (doc 16 §9 point 5). Enregistrement idempotent, jamais de mise
  à jour silencieuse d'une config comptable.

## Statuts

- **Depuis le 2026-11-05** : plus aucun dossier de démo en base ; les
  dossiers viennent de l'import Digifactory (doc 17) ;
  le gestionnaire ne voit que ceux de son `tenant_id`. **Isolation dans les
  requêtes du repository, pas de RLS Postgres** (V1). Un seul portefeuille
  de démo, pas encore de création de dossier hors amorçage.
- **V1 (doc 12, phase 1.1)** : multi-tenant complet, ~200 dossiers
  indépendants, matrice statut × pack pleinement opérationnelle.

## Doc de référence

[doc 03 §3bis](../../../docs/03-architecture.md#3bis-les-deux-axes-de-configuration--statut-du-dossier--pack-métier),
[doc 06 §7](../../../docs/06-moteur-comptable.md#7-multi-statuts--matrice-de-paramétrage-le-cœur-de-la-versatilité),
[doc 17 §3](../../../docs/archive/17-plan-demo-journal-2026-09.md#3-coupes-de-scope-assumées).
