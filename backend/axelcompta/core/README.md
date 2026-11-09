# core/

Types et primitives partagés par tout le reste du monolithe. Le seul module
dont tous les autres ont le droit de dépendre.

**Dépendances :** aucune (module racine).

## Fichiers

- `money.py` — `Money` (centimes int) + addition minimale (`__add__`,
  `zero`, `somme`), refuse les devises différentes.
- `errors.py` — `DomaineError`, `InvariantViole`.
- `ids.py` — identifiants typés (`DossierId`, `EcritureId`, `TransactionId`...).
- `db.py` — bootstrap SQLAlchemy (métadonnées partagées, moteur).
- `libelles.py` — l'ancien suffixe « (catégorie) » des libellés d'écriture
  (AXE-848) : `sans_categorie()` à l'affichage et à l'export,
  `categorie_du_suffixe()` en repli pour les écritures d'avant le 9 nov.
- `pcg.py` — `nature_depuis_compte()` (**fait, semaine 3**) : convention PCG
  générique classe 6 = charge / classe 7 = produit. Volontairement ici et
  pas dans `packs/` : ce n'est pas une règle spécifique au pack VTC.

## Statuts

- **Démo (doc 17, semaines 0-3)** : `Money`, ids typés, `pcg.py` — le
  strict nécessaire pour faire tourner le pipeline bout-en-bout et calculer
  un compte de résultat/bilan simplifiés.
- **V1 (doc 12, phase 1.1)** : `core/` complet avec tests de propriétés
  (property-based testing) sur `Money` et les erreurs.

## Doc de référence

[doc 03 §2](../../../docs/03-architecture.md#2--stack-retenue) (choix Pydantic v2),
[doc 06 §1](../../../docs/06-moteur-comptable.md#1-invariants-absolus-violations--bug-bloquant-jamais-contournable) (invariants Money),
[doc 09 §2](../../../docs/09-strategie-tests.md#2-tests-unitaires-et-de-propriétés-le-socle).
