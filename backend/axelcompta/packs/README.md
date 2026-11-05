# packs/

Le deuxième axe de configuration (voir aussi [`tenants/`](../tenants/README.md)
pour le premier) : le **pack métier** — taxonomie de catégories, règles
système, templates d'écritures sectoriels, paramètres d'anomalies, adaptation
ML. Un pack est un ensemble de **données versionnées** (+ ses tests), pas du
code : `if secteur == "vtc"` est interdit hors de ce module.

**Dépendances :** `core`.

## Ce qui existe déjà et sera réutilisé

Le pack **VTC** (le premier) est déjà largement dégrossi dans l'audit,
inchangé à cet endroit :

- [`_AUDIT_DONNEES/packs_vtc/taxonomie.md`](../../../_AUDIT_DONNEES/packs_vtc/taxonomie.md) — 29 catégories décrites (+ 1 bucket technique résiduel).
- [`_AUDIT_DONNEES/packs_vtc/regles_regex.csv`](../../../_AUDIT_DONNEES/packs_vtc/regles_regex.csv) — 12 règles regex (déjà la version réduite pour la démo).
- [`_AUDIT_DONNEES/packs_vtc/mapping_pcg_categorie.csv`](../../../_AUDIT_DONNEES/packs_vtc/mapping_pcg_categorie.csv) — 71 comptes PCG mappés vers 29 catégories.

`vtc_demo.py` charge ces deux CSV directement (fait, semaine 2) : ni
dupliqués, ni réencodés — `packs/` sera la version *packagée et validée
par un expert-comptable* de ces artefacts pour la V1.

## Statuts

- **Démo (doc 17 §4bis, semaine 2, fait)** : `charger_regles()` (12 règles),
  `charger_compte_par_categorie()` (premier compte listé par catégorie —
  choix déterministe, **pas un jugement comptable validé**). `nature_depuis_compte()`
  est ré-exportée ici pour compat mais vit maintenant dans
  `core/pcg.py` (semaine 3) : ce n'est pas une règle spécifique au pack VTC.
- **Bug trouvé en testant sur 3 vrais dossiers complets (2026-09-05, doc 17
  §7bis/semaine 4)** : `charger_regles()` force maintenant `re.IGNORECASE`
  sur les 12 règles. Une seule (`carburant`) avait `(?i)` inline dans le CSV
  du pack ; les 11 autres — dont `recettes_plateformes`, le revenu principal
  d'un chauffeur — ne matchaient donc jamais un libellé bancaire en
  MAJUSCULES (le format usuel des relevés). Sur un dossier réel testé, le
  chiffre d'affaires détecté est passé de 591 € à 11 937 € une fois corrigé.
  **Écart résiduel assumé, pas un bug** : ~29 000 € de CA réel sur ce
  dossier, le reste correspond à des libellés sans nom de plateforme (ex.
  « REGUL FACT DIVERS PRESTATIONS SERVICES ») — une vraie limite de
  couverture du pack (12 règles, doc 12 §2.1 en prévoit 100-200 pour la V1),
  pas quelque chose que `re.IGNORECASE` peut résoudre. Corrigé au
  chargement, pas dans le CSV source (toujours un brouillon d'audit).
- **Au 2026-11-05** : toujours les 12 règles de l'audit
  (`_AUDIT_DONNEES/packs_vtc/regles_regex.csv`), plus les règles génériques
  de `categorize/`. Mesure sur le premier flux réel : AXE-732. Relecture
  de la taxonomie par un expert-comptable : AXE-815.
- **V1 (doc 12, phase 1.1 + 0.2)** : taxonomie complète et mapping
  compte-par-catégorie validés avec le comptable du client (aujourd'hui un
  brouillon d'audit, premier compte listé pris arbitrairement).

## Doc de référence

[doc 03 §3bis](../../../docs/03-architecture.md#3bis-les-deux-axes-de-configuration--statut-du-dossier--pack-métier),
[doc 07 §3](../../../docs/07-ml-donnees-entrainement.md#3-features-et-modèle).
