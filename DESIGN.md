---
version: 1.0
name: AxeLCompta-design-system
description: |
  AxeLCompta est un outil B2B de production comptable : interface de
  professionnels (gestionnaire de portefeuille, comptable), pas du grand public.
  Le parti pris est le calme visuel — fond blanc, blancs généreux, une seule
  couleur d'accent (bleu professionnel), Inter partout, coins arrondis discrets,
  ombres légères. Les chiffres ont leur propre traitement typographique
  (tabular-nums, alignement à droite, codage couleur positif/négatif).
  L'interface s'adapte à deux modes (portefeuille N dossiers vs mono-entreprise)
  et au statut de chaque dossier — sans jamais afficher de fonctions grisées.
  Référence d'inspiration : docs/archive/DESIGN-revolut.md

colors:
  # --- Marque ---
  primary: "#2563EB"
  primary-bright: "#3B82F6"
  primary-deep: "#1D4ED8"
  primary-subtle: "#EFF6FF"
  on-primary: "#FFFFFF"

  # --- Neutres (Slate) ---
  ink: "#0F172A"
  body: "#1E293B"
  subtle: "#475569"
  muted: "#5E6C84"
  faint: "#CBD5E1"
  on-dark: "#F8FAFC"
  on-dark-mute: "rgba(248,250,252,0.65)"

  # --- Canvas et surfaces ---
  canvas: "#FFFFFF"
  canvas-app: "#F8FAFC"
  surface-raised: "#FFFFFF"
  surface-soft: "#F1F5F9"
  surface-overlay: "#FFFFFF"
  surface-dark: "#0F172A"
  surface-dark-raised: "#1E293B"

  # --- Bordures ---
  border: "#E2E8F0"
  border-strong: "#CBD5E1"
  border-focus: "#2563EB"
  hairline: "#F1F5F9"

  # --- Sémantiques générales ---
  success: "#15803D"
  success-subtle: "#F0FDF4"
  success-border: "#86EFAC"
  warning: "#B45309"
  warning-subtle: "#FFFBEB"
  warning-border: "#FCD34D"
  danger: "#D42626"
  danger-subtle: "#FEF2F2"
  danger-border: "#FCA5A5"
  info: "#0369A1"
  info-subtle: "#F0F9FF"
  info-border: "#7DD3FC"

  # --- Sémantiques comptables ---
  amount-positive: "#15803D"
  amount-negative: "#D42626"
  amount-neutral: "#0F172A"
  validated: "#15803D"
  validated-subtle: "#F0FDF4"
  pending: "#B45309"
  pending-subtle: "#FFFBEB"
  auto-rule: "#0369A1"
  auto-rule-subtle: "#F0F9FF"
  auto-ml: "#7C3AED"
  auto-ml-subtle: "#F5F3FF"
  auto-llm: "#9333EA"
  auto-llm-subtle: "#FAF5FF"
  alert-anomaly: "#D42626"
  alert-anomaly-subtle: "#FEF2F2"
  missing: "#5E6C84"
  closed: "#475569"
  closed-subtle: "#F8FAFC"

typography:
  # --- Titres de pages et dashboard ---
  display-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.21
    letterSpacing: -0.28px
  display-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: 700
    lineHeight: 1.27
    letterSpacing: -0.22px

  # --- Titres de sections et panneaux ---
  heading-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.44
    letterSpacing: -0.09px
  heading-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  heading-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.43
    letterSpacing: 0

  # --- Corps de texte ---
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: 0
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.38
    letterSpacing: 0

  # --- Montants (tabular-nums — CRITIQUE pour l'alignement comptable) ---
  amount-xl:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.25
    fontVariantNumeric: tabular-nums
    letterSpacing: -0.24px
  amount-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.33
    fontVariantNumeric: tabular-nums
    letterSpacing: 0
  amount-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.4
    fontVariantNumeric: tabular-nums
    letterSpacing: 0
  amount-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.38
    fontVariantNumeric: tabular-nums
    letterSpacing: 0
  amount-xs:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.33
    fontVariantNumeric: tabular-nums
    letterSpacing: 0

  # --- UI ---
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.43
    letterSpacing: 0
  label-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.38
    letterSpacing: 0
  button-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.43
    letterSpacing: 0
  button-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.38
    letterSpacing: 0
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.33
    letterSpacing: 0
  caption-strong:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: 0.12px
  code:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0

rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  full: 9999px

spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  xxxl: 48px
  section: 64px

shadow:
  none: none
  xs: "0 1px 2px rgba(15,23,42,0.06)"
  sm: "0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04)"
  md: "0 4px 6px -1px rgba(15,23,42,0.08), 0 2px 4px -2px rgba(15,23,42,0.04)"
  lg: "0 10px 15px -3px rgba(15,23,42,0.08), 0 4px 6px -4px rgba(15,23,42,0.04)"
  overlay: "0 20px 25px -5px rgba(15,23,42,0.10), 0 8px 10px -6px rgba(15,23,42,0.04)"

transition:
  fast: "100ms ease"
  base: "150ms ease"
  slow: "200ms ease"

components:
  # --- Boutons ---
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: 7px 16px
    height: 36px
    hoverBackground: "{colors.primary-bright}"
    activeBackground: "{colors.primary-deep}"
    transition: "{transition.base}"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button-md}"
    border: "1px solid {colors.border-strong}"
    rounded: "{rounded.md}"
    padding: 6px 15px
    height: 36px
    hoverBackground: "{colors.canvas-app}"
    transition: "{transition.base}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.subtle}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 36px
    hoverBackground: "{colors.surface-soft}"
    hoverTextColor: "{colors.ink}"
    transition: "{transition.base}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: 7px 16px
    height: 36px
    transition: "{transition.base}"
  button-sm:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-sm}"
    rounded: "{rounded.sm}"
    padding: 4px 12px
    height: 28px
    transition: "{transition.base}"
  button-sm-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.subtle}"
    typography: "{typography.button-sm}"
    rounded: "{rounded.sm}"
    padding: 4px 10px
    height: 28px
    hoverBackground: "{colors.surface-soft}"
    transition: "{transition.base}"

  # --- Champs de saisie ---
  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    placeholderColor: "{colors.muted}"
    typography: "{typography.body-md}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 36px
    focusBorder: "{colors.border-focus}"
    focusRing: "0 0 0 3px rgba(37,99,235,0.12)"
    transition: "{transition.fast}"
  text-input-lg:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    placeholderColor: "{colors.muted}"
    typography: "{typography.body-lg}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.md}"
    padding: 10px 14px
    height: 44px
    focusBorder: "{colors.border-focus}"
    focusRing: "0 0 0 3px rgba(37,99,235,0.12)"
  select:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 36px
    focusBorder: "{colors.border-focus}"
    focusRing: "0 0 0 3px rgba(37,99,235,0.12)"

  # --- Cards et panneaux ---
  card:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.lg}"
    padding: 20px
    shadow: "{shadow.xs}"
  card-flat:
    backgroundColor: "{colors.canvas-app}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 16px
  card-section:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.lg}"
    padding: 0
    shadow: "{shadow.sm}"
  card-warning:
    backgroundColor: "{colors.warning-subtle}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.warning-border}"
    rounded: "{rounded.md}"
    padding: 14px 16px
  card-danger:
    backgroundColor: "{colors.danger-subtle}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.danger-border}"
    rounded: "{rounded.md}"
    padding: 14px 16px
  card-info:
    backgroundColor: "{colors.info-subtle}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.info-border}"
    rounded: "{rounded.md}"
    padding: 14px 16px

  # --- Ligne de transaction (élément le plus fréquent du produit) ---
  transaction-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    height: 52px
    padding: 0 16px
    borderBottom: "1px solid {colors.border}"
    hoverBackground: "{colors.canvas-app}"
    transition: "{transition.fast}"
  transaction-row-selected:
    backgroundColor: "{colors.primary-subtle}"
    borderLeft: "2px solid {colors.primary}"
    transition: "{transition.fast}"
  transaction-row-alert:
    backgroundColor: "{colors.danger-subtle}"
    borderLeft: "2px solid {colors.danger}"

  # --- Carte de revue (file de revue — écran principal) ---
  review-card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.lg}"
    padding: 24px
    shadow: "{shadow.md}"
  review-card-source-rule:
    accentColor: "{colors.auto-rule}"
    accentBackground: "{colors.auto-rule-subtle}"
  review-card-source-ml:
    accentColor: "{colors.auto-ml}"
    accentBackground: "{colors.auto-ml-subtle}"
  review-card-source-llm:
    accentColor: "{colors.auto-llm}"
    accentBackground: "{colors.auto-llm-subtle}"

  # --- Badges de statut (vocabulaire unique du produit) ---
  badge-validated:
    backgroundColor: "{colors.validated-subtle}"
    textColor: "{colors.validated}"
    border: "1px solid {colors.success-border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-pending:
    backgroundColor: "{colors.pending-subtle}"
    textColor: "{colors.pending}"
    border: "1px solid {colors.warning-border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-auto-rule:
    backgroundColor: "{colors.auto-rule-subtle}"
    textColor: "{colors.auto-rule}"
    border: "1px solid {colors.info-border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-auto-ml:
    backgroundColor: "{colors.auto-ml-subtle}"
    textColor: "{colors.auto-ml}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-auto-llm:
    backgroundColor: "{colors.auto-llm-subtle}"
    textColor: "{colors.auto-llm}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-alert:
    backgroundColor: "{colors.alert-anomaly-subtle}"
    textColor: "{colors.alert-anomaly}"
    border: "1px solid {colors.danger-border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-missing:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    border: "1px dashed {colors.border-strong}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-closed:
    backgroundColor: "{colors.closed-subtle}"
    textColor: "{colors.closed}"
    border: "1px solid {colors.border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px

  # --- Montants (affichage comptable) ---
  amount-positive:
    textColor: "{colors.amount-positive}"
    typography: "{typography.amount-md}"
    textAlign: right
  amount-negative:
    textColor: "{colors.amount-negative}"
    typography: "{typography.amount-md}"
    textAlign: right
  amount-neutral:
    textColor: "{colors.amount-neutral}"
    typography: "{typography.amount-md}"
    textAlign: right
  amount-large-positive:
    textColor: "{colors.amount-positive}"
    typography: "{typography.amount-lg}"
    textAlign: right
  amount-large-negative:
    textColor: "{colors.amount-negative}"
    typography: "{typography.amount-lg}"
    textAlign: right

  # --- Tableaux comptables (journaux, grand livre, balance) ---
  table-header:
    backgroundColor: "{colors.canvas-app}"
    textColor: "{colors.subtle}"
    typography: "{typography.caption-strong}"
    borderBottom: "1px solid {colors.border}"
    height: 36px
    padding: 0 16px
    letterSpacing: 0.3px
    textTransform: uppercase
  table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    borderBottom: "1px solid {colors.hairline}"
    height: 52px
    padding: 0 16px
    hoverBackground: "{colors.canvas-app}"
    transition: "{transition.fast}"
  table-row-total:
    backgroundColor: "{colors.canvas-app}"
    textColor: "{colors.ink}"
    typography: "{typography.heading-sm}"
    borderTop: "2px solid {colors.border-strong}"
    height: 44px
    padding: 0 16px
  table-cell-amount:
    textAlign: right
    fontVariantNumeric: tabular-nums
    paddingRight: 16px

  # --- Navigation (sidebar sombre) ---
  sidebar:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    width: 240px
    padding: 12px 8px
  sidebar-header:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.heading-sm}"
    padding: 12px 12px 8px 12px
    borderBottom: "1px solid rgba(248,250,252,0.08)"
  sidebar-section-label:
    textColor: "rgba(248,250,252,0.40)"
    typography: "{typography.caption-strong}"
    letterSpacing: 0.6px
    textTransform: uppercase
    padding: 14px 12px 4px 12px
  sidebar-item:
    backgroundColor: "transparent"
    textColor: "{colors.on-dark-mute}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 34px
    hoverBackground: "rgba(248,250,252,0.07)"
    hoverTextColor: "{colors.on-dark}"
    transition: "{transition.fast}"
  sidebar-item-active:
    backgroundColor: "rgba(37,99,235,0.25)"
    textColor: "{colors.on-dark}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 34px

  # --- En-tête de page (top bar) ---
  top-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    borderBottom: "1px solid {colors.border}"
    height: 56px
    padding: 0 24px

  # --- Raccourcis clavier (affichés dans l'UI) ---
  kbd:
    backgroundColor: "{colors.canvas-app}"
    textColor: "{colors.subtle}"
    typography: "{typography.caption}"
    border: "1px solid {colors.border-strong}"
    rounded: "{rounded.xs}"
    padding: 1px 5px
    shadow: "0 1px 0 {colors.border-strong}"

  # --- Alerte d'anomalie (instruction) ---
  anomaly-card:
    backgroundColor: "{colors.canvas}"
    border: "1px solid {colors.danger-border}"
    rounded: "{rounded.lg}"
    padding: 20px
    shadow: "{shadow.sm}"
    accentBarColor: "{colors.danger}"
    accentBarWidth: 3px

  # --- Page de signature (vue mobile-first du chauffeur) ---
  signature-page:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    maxWidth: 600px
    padding: 24px 16px
  signature-summary:
    backgroundColor: "{colors.canvas-app}"
    rounded: "{rounded.lg}"
    border: "1px solid {colors.border}"
    padding: 20px
  signature-cta:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    height: 48px
    width: "100%"

  # --- État vide (empty state) ---
  empty-state:
    textColor: "{colors.muted}"
    typography: "{typography.body-md}"
    iconColor: "{colors.faint}"
    padding: 48px 24px
    textAlign: center

  # --- Toasts et notifications ---
  toast-success:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    border: "1px solid rgba(248,250,252,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.success}"
  toast-warning:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    border: "1px solid rgba(248,250,252,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.warning}"
  toast-error:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    border: "1px solid rgba(248,250,252,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.danger}"

  # --- Modals ---
  modal-overlay:
    backgroundColor: "rgba(15,23,42,0.50)"
  modal:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.xl}"
    padding: 24px
    shadow: "{shadow.overlay}"
    maxWidth: 520px
---

## Vue d'ensemble

AxeLCompta adopte un **système canvas clair** : le fond de l'application est
`{colors.canvas-app}` (`#F8FAFC`), les cards et surfaces en relief sont en
`{colors.canvas}` (`#FFFFFF`) avec une bordure `{colors.border}` légère et
une ombre `{shadow.xs}`. Le contraste se joue en douceur — jamais de noir
pur sur blanc pur, toujours le `{colors.ink}` (`#0F172A`) légèrement chaud.

L'exception est la **sidebar** : fond `{colors.surface-dark}` (`#0F172A`)
avec texte `{colors.on-dark-mute}`, qui ancre l'interface sans agressivité.
C'est le seul endroit sombre de l'app en V1 (le mode sombre global est en
phase 2).

L'**accent bleu** (`{colors.primary}` — `#2563EB`) apparaît exclusivement
sur les boutons d'action primaires, les bordures de focus, les éléments
sélectionnés, et l'item actif de la sidebar. Partout ailleurs : neutres.

## Couleurs

### Marque

- **Primary** (`{colors.primary}` — `#2563EB`) : bleu professionnel. Bouton
  d'action principal, focus ring, item sidebar actif, lien. Un seul accent —
  ne jamais en introduire un second sans décision explicite (ADR).
- **Primary Bright** (`{colors.primary-bright}` — `#3B82F6`) : état hover sur
  les éléments bleus.
- **Primary Deep** (`{colors.primary-deep}` — `#1D4ED8`) : état pressed/active.
- **Primary Subtle** (`{colors.primary-subtle}` — `#EFF6FF`) : fond de
  transaction sélectionnée, highlight de focus contextuel.

### Neutrals

Toute la gamme est issue du continuum **Slate** (froid, précis) :

- `{colors.ink}` (`#0F172A`) : titres, texte principal.
- `{colors.body}` (`#1E293B`) : corps de texte long.
- `{colors.subtle}` (`#475569`) : labels, métadonnées, en-têtes de colonnes.
- `{colors.muted}` (`#5E6C84`) : placeholders, texte désactivé, états vides. Assombri pour le contraste AA (4,5:1) sur blanc et sur `surface-soft`.
- `{colors.faint}` (`#CBD5E1`) : icônes d'état vide, éléments quasi-invisibles.

### Surfaces

- **Canvas App** (`{colors.canvas-app}` — `#F8FAFC`) : fond de l'application
  (body). Ne jamais poser du blanc pur sur blanc pur.
- **Canvas** (`{colors.canvas}` — `#FFFFFF`) : cards, panneaux, tableaux.
- **Surface Soft** (`{colors.surface-soft}` — `#F1F5F9`) : fond de l'en-tête
  des tableaux, états hover légers, pills de filtre.

### Sémantiques comptables

Ces couleurs ont un sens métier précis — ne jamais les détourner :

| Token | Hex | Usage strict |
|---|---|---|
| `{colors.amount-positive}` | `#15803D` | Recettes, soldes créditeurs, montants positifs |
| `{colors.amount-negative}` | `#D42626` | Charges, soldes débiteurs, montants négatifs |
| `{colors.validated}` | `#15803D` | Badge « validé », écriture confirmée par un humain |
| `{colors.pending}` | `#B45309` | Badge « à valider », en attente de décision |
| `{colors.auto-rule}` | `#0369A1` | Catégorisé par une règle déterministe |
| `{colors.auto-ml}` | `#7C3AED` | Catégorisé par le modèle ML |
| `{colors.auto-llm}` | `#9333EA` | Catégorisé par le LLM |
| `{colors.alert-anomaly}` | `#D42626` | Alerte anomalie / abus potentiel |
| `{colors.missing}` | `#5E6C84` | Justificatif manquant (neutre, non bloquant) |
| `{colors.closed}` | `#475569` | Exercice clôturé (lecture seule) |

## Typographie

Une seule famille : **Inter** (open-source, Google Fonts). Police de corps
d'Inter à weight 400, labels à 500, titres et boutons à 600-700.

### Règle des montants — invariant non négociable

Tout montant affiché dans l'interface **doit** utiliser un token
`{typography.amount-*}` qui inclut `fontVariantNumeric: tabular-nums`.
Cela garantit l'alignement vertical des colonnes de chiffres (les `1` et
les `9` occupent la même largeur). Ne jamais afficher un montant avec
`{typography.body-md}` — même en passant, même en dev.

Format monétaire français : `1 234,56 €` (espace fine insécable comme
séparateur de milliers, virgule décimale). Utiliser `Intl.NumberFormat`
avec `locale: 'fr-FR'`, `style: 'currency'`, `currency: 'EUR'`.

Montants négatifs : couleur `{colors.amount-negative}`, jamais de parenthèses.
Montants positifs : couleur `{colors.amount-positive}` dans un tableau de
recettes, `{colors.amount-neutral}` dans un formulaire de saisie neutre.

### Hiérarchie

| Token | Taille | Poids | Utilisation principale |
|---|---|---|---|
| `{typography.display-lg}` | 28px / 700 | Titre de page, dashboard principal |
| `{typography.display-md}` | 22px / 700 | Titre de section majeure |
| `{typography.heading-lg}` | 18px / 600 | Titre de panneau, modale |
| `{typography.heading-md}` | 16px / 600 | Sous-titre, en-tête de groupe |
| `{typography.heading-sm}` | 14px / 600 | Label de champ, en-tête de colonne |
| `{typography.body-lg}` | 16px / 400 | Texte explicatif long (rare) |
| `{typography.body-md}` | 14px / 400 | Texte courant, libellés de transaction |
| `{typography.body-sm}` | 13px / 400 | Notes, historique compact |
| `{typography.amount-xl}` | 24px / 700 | Solde total du portefeuille |
| `{typography.amount-lg}` | 18px / 600 | Solde d'un dossier, total de période |
| `{typography.amount-md}` | 15px / 500 | Montant dans une ligne de tableau |
| `{typography.amount-sm}` | 13px / 500 | Montant secondaire, récapitulatif |
| `{typography.label-md}` | 14px / 500 | Libellé de formulaire, nav sidebar |
| `{typography.button-md}` | 14px / 600 | Label de bouton standard |
| `{typography.caption}` | 12px / 400 | Date, source, métadonnée compacte |
| `{typography.code}` | 13px / 400 mono | Numéro de compte PCG, SIREN, IBAN |

## Layout

### Application shell

```
┌─────────────────────────────────────────────────────────────┐
│  Top Bar (56px) — Logo · Recherche globale (⌘K) · User     │
├────────────────┬────────────────────────────────────────────┤
│                │                                            │
│  Sidebar       │  Zone de contenu principale                │
│  240px         │  canvas-app (#F8FAFC)                      │
│  surface-dark  │  padding : 24px                            │
│                │                                            │
└────────────────┴────────────────────────────────────────────┘
```

En mode mono-entreprise, la sidebar reste présente mais la liste des dossiers
est supprimée — l'item racine mène directement au tableau de bord du dossier.

### Espacement

- **Padding de page** : `{spacing.xl}` (24px) sur les quatre côtés.
- **Gap entre cards** : `{spacing.lg}` (16px).
- **Padding interne card** : `{spacing.xl}` (20px) standard, `{spacing.xxl}`
  (24px) pour les modales et la review-card.
- **Hauteur de ligne de tableau** : 52px (`{component.table-row}`) — permet
  de voir le contenu sans rembourrage excessif sur un portefeuille de 200
  dossiers.

### Grille de contenu

- **Max-width** : 1280px sur la zone de contenu (hors sidebar).
- **Tableaux** : pleine largeur de la zone de contenu.
- **Dashboard portefeuille** : grille 3 colonnes à ≥ 1024px, 2 à ≥ 768px, 1 en
  dessous.
- **File de revue** : colonne unique centrée, max-width 720px — concentration
  maximale.

## Élévation et profondeur

Le système évite les ombres dramatiques. La profondeur vient du contraste
canvas-app / canvas :

| Niveau | Traitement | Usage |
|---|---|---|
| 0 — fond app | `{colors.canvas-app}` sans ombre | Body, fond de page |
| 1 — surface | `{colors.canvas}` + `{shadow.xs}` + bordure | Cards, tableaux |
| 2 — panneau flottant | `{colors.canvas}` + `{shadow.md}` + bordure | Dropdowns, popovers |
| 3 — overlay | `{colors.canvas}` + `{shadow.overlay}` + bordure | Modales |
| S — sidebar | `{colors.surface-dark}` — ancrage, sans ombre | Navigation principale |

Pas de gradient, pas d'effet glassmorphism, pas de fond flouté.

## Formes

- `{rounded.full}` — badges, pills de filtre, tags.
- `{rounded.lg}` (12px) — cards, modales, review-card.
- `{rounded.md}` (8px) — boutons, champs, dropdowns, toasts.
- `{rounded.sm}` (6px) — boutons small, kbd.
- `{rounded.xs}` (4px) — chips internes, petits éléments.
- `{rounded.none}` — tableaux full-width, top bar, sidebar.

## Composants clés

### Boutons

**`button-primary`** — action principale de la page
- Bleu primaire, texte blanc, `rounded.md`, 36px de haut.
- Un seul par écran au maximum (parfois zéro — la file de revue fonctionne au
  clavier, les boutons sont secondaires).

**`button-secondary`** — action alternative
- Canvas blanc, bordure, texte ink. Toujours en accompagnement d'un
  `button-primary`, jamais seul sur un écran.

**`button-ghost`** — action tertiaire ou de navigation
- Transparent, texte `{colors.subtle}`, fond au hover. Pour les actions de
  moindre importance (« Annuler », actions inline sur une ligne de tableau).

**`button-danger`** — action destructive
- Rouge, réservé aux confirmations de suppression. Toujours dans une modale de
  confirmation, jamais directement accessible sur une liste.

### File de revue (`review-card`)

L'écran le plus utilisé du produit. Règles strictes :

- Une seule `review-card` visible à la fois, centrée, max-width 720px.
- La **source de la proposition** est visuellement distincte avec l'accent
  correspondant (`auto-rule` → bleu, `auto-ml` → violet, `auto-llm` → violet
  plus profond) — l'utilisateur sait en un coup d'œil pourquoi cette
  proposition a été faite.
- Les **raccourcis clavier** (`{component.kbd}`) sont affichés à côté de chaque
  action : `A` Accepter, `1-3` Alternatives, `R` Rechercher, `S` Passer,
  `J` Joindre.
- Montant affiché en `{typography.amount-lg}` avec la couleur appropriée.
- Jamais de spinner plein écran entre deux transactions — transition instantanée
  ou squelette léger.

### Tableaux comptables

Les tableaux sont le cœur de l'interface comptable. Règles :

- En-tête : `{component.table-header}` — fond `canvas-app`, texte `subtle`,
  uppercase, 12px. Toujours fixe (sticky) sur les tableaux longs.
- Lignes : `{component.table-row}` — 52px de haut, hover `canvas-app`.
- Colonnes de montants : **toujours alignées à droite**, tabular-nums.
- Ligne de total : `{component.table-row-total}` — fond `canvas-app`, weight 600,
  bordure supérieure double.
- Virtualisation obligatoire (TanStack Virtual) au-delà de 100 lignes — le grand
  livre peut dépasser 10 000 lignes pour un dossier actif.

### Badges de statut

Vocabulaire unique — un seul badge par objet à la fois :

| Badge | Quand |
|---|---|
| `badge-validated` | Écriture validée par un humain |
| `badge-pending` | Proposition en attente de décision |
| `badge-auto-rule` | Catégorisé par règle déterministe |
| `badge-auto-ml` | Catégorisé par ML |
| `badge-auto-llm` | Catégorisé par LLM |
| `badge-alert` | Anomalie ouverte sur la transaction |
| `badge-missing` | Justificatif attendu mais absent (non bloquant) |
| `badge-closed` | Appartient à un exercice clôturé |

Ne jamais créer de badge ad hoc. Si un état manque, ouvrir une discussion sur
le vocabulaire avant d'ajouter un token.

### Page de signature (chauffeur — mobile-first)

Cet écran est vu par les gérants (chauffeurs), pas par les pros de la compta.
Règles distinctes :

- Max-width 600px, centré.
- Taille de bouton CTA : 48px de haut, pleine largeur — target tactile
  confortable.
- Résumé en langage clair AVANT le PDF (jamais juste un PDF brut).
- Zéro création de compte, zéro jargon comptable.
- Aucun élément du design system interne (sidebar, table-header, etc.)
  n'apparaît sur cette page.

## Do's et Don'ts

### Do

- Poser tout contenu sur `{colors.canvas-app}` comme fond de page. Jamais de
  blanc pur (`#FFFFFF`) comme fond body — utiliser canvas uniquement pour les
  cards.
- Afficher tous les montants avec un token `{typography.amount-*}` et
  `tabular-nums`. Aucune exception.
- Coder les montants négatifs en `{colors.amount-negative}` et positifs en
  `{colors.amount-positive}`. Jamais de parenthèses, jamais de symbole `+/-`
  seul sans couleur.
- Utiliser le vocabulaire de badge exact (proposé / validé / clôturé / etc.) —
  doc 11 §4 définit ces termes, ils sont contrats avec l'utilisateur.
- Afficher les raccourcis clavier dans la file de revue — les pros vivent au
  clavier.
- Utiliser `{shadow.xs}` ou `{shadow.sm}` pour les cards, pas au-delà (sauf
  modales).
- Tout état vide a une action — jamais de page blanche sans invitation.
- Transitions à 150ms (`{transition.base}`) maximum — l'interface doit sembler
  réactive, pas animée.

### Don't

- Ne pas introduire de deuxième couleur d'accent sans ADR. Le bleu primary est
  le seul stamp de marque.
- Ne pas utiliser `{colors.amount-positive}` ou `{colors.amount-negative}` pour
  autre chose que des montants — la couleur verte ne signifie pas « succès » sur
  un bouton dans ce contexte.
- Ne pas afficher de pages grisées pour les fonctionnalités non applicables au
  statut du dossier. Si une feature n'existe pas pour ce dossier, ne pas la
  montrer.
- Ne pas utiliser de spinner plein écran. Toujours des squelettes.
- Ne pas écrire de messages d'erreur avec des codes techniques (`Error 500`,
  `ECONNREFUSED`). Toujours un message humain + une action de récupération.
- Ne pas qualifier une anomalie juridiquement dans l'UI (`fraude`, `abus`).
  Toujours `à justifier`, `hors profil`, `à instruire`.
- Ne pas poser de `box-shadow` au-delà de `{shadow.md}` hors modales. Pas de
  `drop-shadow` décoratif.
- Ne pas mélanger Aeonik Pro, Geist ou toute autre font d'affichage : Inter
  uniquement, pour tous les usages, dans toute l'app.

## Comportement responsive

L'interface est B2B desktop-first. La page de signature est l'exception
mobile-first.

| Breakpoint | Largeur | Changements principaux |
|---|---|---|
| Desktop XL | ≥ 1440px | Grille dashboard 3 colonnes, tableaux pleine largeur |
| Desktop | 1280–1439px | Idem, container légèrement réduit |
| Laptop | 1024–1279px | Grille dashboard 2 colonnes |
| Tablet | 768–1023px | Sidebar réduite à 56px (icônes seules) ; grille 1 colonne |
| Mobile | < 768px | Sidebar masquée (drawer) ; uniquement pour la page de signature |

La sidebar collapse à 56px (icônes seules) à partir de 1023px. En dessous de
768px, elle devient un drawer — le seul cas d'usage mobile en V1 est la page de
signature, qui est une page publique autonome sans sidebar.

## Accessibilité

- Contrastes WCAG AA obligatoires sur tous les textes. Vérifier avec Radix
  Colors ou Tailwind Contrast Checker avant tout nouveau token de couleur.
- Focus ring visible sur tous les éléments interactifs : `{colors.border-focus}`
  avec `focusRing` à 3px (`box-shadow: 0 0 0 3px rgba(37,99,235,0.12)`).
- Navigation clavier complète — les professionnels vivent au clavier, notamment
  dans la file de revue.
- Touch targets minimum 44px sur les éléments mobiles (page de signature et habillage chauffeur). Les champs du chauffeur font 16px : en dessous, iOS zoome au focus. Aucun texte chauffeur sous 12px.
- Pas de couleur comme seul vecteur d'information : les montants négatifs ont
  la couleur ET le signe `-` ; les badges ont la couleur ET le texte.

## Correspondance Tailwind / shadcn-ui

Le projet utilise **Tailwind CSS v4** + shadcn/ui (migré depuis v3 le
2026-09-22 — le CLI shadcn actuel ne génère que du code v4). Les tokens
DESIGN.md vivent dans un bloc `@theme` (`frontend/app/globals.css`, valeurs
hex directes, pas de triplet RGB — Tailwind v4 n'en a plus besoin) : c'est
la source de vérité pour tout ce qui est spécifique au produit
(`--color-primary`, `--color-ink`, `--color-auto-ml`, etc., préfixe
`--color-*` obligatoire en v4 pour que Tailwind génère les classes `bg-*`/
`text-*` correspondantes).

Les variables génériques shadcn (celles que les composants `ui/*` générés
par le CLI référencent — `--background`, `--foreground`, `--card`,
`--primary`, `--secondary`, `--muted`, `--destructive`, `--border`,
`--input`, `--ring`) vivent dans un second bloc `:root`, **remplacées avec
les vraies valeurs DESIGN.md** (le CLI génère par défaut une palette grise
neutre — toujours l'écraser, jamais la garder telle quelle) :

```css
:root {
  --background: #f8fafc;   /* canvas-app */
  --foreground: #0f172a;   /* ink */
  --card: #ffffff;         /* canvas */
  --primary: #2563eb;      /* primary */
  --primary-foreground: #ffffff; /* on-primary */
  --secondary: #ffffff;    /* canvas — button-secondary */
  --muted: #f1f5f9;        /* surface-soft */
  --muted-foreground: #475569; /* subtle */
  --destructive: #dc2626;  /* danger */
  --border: #e2e8f0;       /* border */
  --input: #e2e8f0;        /* border, text-input */
  --ring: #2563eb;         /* border-focus */
  --radius: 0.5rem;        /* rounded.md, 8px */
}
```

Piège vérifié en pratique : `shadcn init`/`add` propose **Geist** comme
police par défaut (preset Nova) — toujours l'écarter, `--font-sans` doit
rester Inter (`next/font/google`), sans exception.

Pour les montants, utiliser la classe utilitaire Tailwind `tabular-nums`
(`font-variant-numeric: tabular-nums`) et ne jamais oublier `text-right` sur
les colonnes numériques.

## Outils de référence

- **Inspiration design** : `docs/archive/DESIGN-revolut.md` — analyse du
  système marketing Revolut, utile pour comprendre la rigueur de tokenisation
  attendue. Ne pas copier les choix visuels (canvas noir, Aeonik Pro) — ils
  sont inadaptés au B2B comptable.
- **Composants** : shadcn/ui comme point de départ, chaque composant personnalisé
  avec les tokens ci-dessus.
- **Storybook** : catalogue vivant du design system — à alimenter en parallèle
  du front (phase 1, tâche 1.4).
- **Validation** : `npx @google/design.md lint DESIGN.md` pour détecter les
  tokens orphelins.

## Known Gaps

- **V1 des composants faite (2026-09-22)**, via shadcn/ui (Radix + CVA) —
  a nécessité de migrer le projet **Tailwind v3 → v4** au passage (le CLI
  shadcn actuel ne génère que du code v4 ; migration faite avec l'outil
  officiel `@tailwindcss/upgrade`, mécanique, un seul renommage
  `shadow-sm` → `shadow-xs`). Composants réels dans
  `frontend/components/ui/` : `Button` (4 variantes DESIGN.md exactement :
  primary/secondary/ghost/danger, tailles default/sm), `Card` (default/
  flat/section/warning/danger/info), `Input` (`uiSize` default/lg — nommé
  ainsi pour ne pas entrer en collision avec l'attribut HTML natif `size`).
  `Badge.tsx` (racine `components/`, pas `ui/`) étendu aux 8 variantes du
  vocabulaire de statut ci-dessus (avant : seulement 4, dont un `danger`
  hors vocabulaire — renommé `alert`) + `neutral`, exception assumée hors
  vocabulaire pour les tags informatifs (régime TVA, plateforme) qui ne
  sont pas un statut d'écriture. Palette `@theme` (`app/globals.css`)
  complétée avec tous les tokens DESIGN.md qui manquaient (`on-primary`,
  `auto-rule`/`auto-ml`/`auto-llm`, `alert-anomaly`, `missing`, `closed`,
  `info`, les couleurs `*-border`) — avant, seul un sous-ensemble existait.
  **Migration complète des écrans faite (même jour)** : dashboard
  gestionnaire (`DossierCard` → `Card`), formulaire d'invitation
  (`InvitationActions` → `Input`/`Button`), `ClotureSection`/
  `GreffeInpiSection` (→ `Card` + `Button`), `TopBar` (déconnexion →
  `Button`), `JustificatifPhoto`/`QuestionCategorisation`/`SignatureMock`
  (→ `Button`/`Input`), pages `/connexion` et `/chauffeur/*` (formulaires →
  `Input uiSize="lg"` + `Button`). `Sidebar` gardée en classes Tailwind
  directes (pas de composant `ui/sidebar` shadcn installé) mais tokens
  corrigés (`on-dark`/`on-dark-mute` au lieu de `white/*` en dur). Plus
  aucun écran du produit n'a de bouton, carte ou champ de saisie en
  classes Tailwind ad hoc. La passe UX/UI proprement dite (revue visuelle,
  pas juste la conformité aux tokens) reste à faire — pas commencée.
  `review-card`, `table-*`, `sidebar-*` (le composant shadcn, pas les
  tokens), `toast-*`, `modal` restent des tokens DESIGN.md sans composant
  React, aucun écran actuel n'en a besoin pour l'instant.
- **Parcours chauffeur : problème plus profond que le design system**
  (retour de Louis, 2026-09-22 soir, doc 17 §14) — l'écran actuel (liste de
  transactions qui défile) n'est pas structuré comme une « app », pas
  seulement mal stylé. Discussion UI + psychologie utilisateur à part
  entière prévue, avant toute nouvelle proposition d'écran — ne pas
  assumer un design ici en attendant.
- Thème sombre (dark mode global) — prévu en phase 5. La sidebar sombre n'est
  pas un dark mode, c'est un choix délibéré de contraste de navigation.
- États disabled non documentés sur les boutons et inputs — à ajouter quand
  les premiers formulaires sont implémentés.
- Design system Figma — les maquettes des 3 écrans clés (doc 12, tâche 0.3)
  doivent utiliser ces tokens comme source de vérité, pas l'inverse.
- Animations et micro-interactions au-delà des transitions de base — hors scope
  V1.
