---
version: 2.0
name: AxeLCompta-design-system
description: |
  AxeLCompta est un outil B2B de production comptable : interface de
  professionnels (gestionnaire de portefeuille, comptable), pas du grand public.
  Le parti pris est un design monochrome, dans l'esprit d'un carnet de
  comptable : fond blanc cassé, texte et bouton principal à l'encre (noir
  chaud), un seul accent orange foncé (signal) pour les repères et les liens
  d'action, un surligneur jaune pour le chiffre qui compte. Inter partout,
  titres à 600, cartes cernées d'un filet plutôt que d'une ombre, navigation
  en barre horizontale. Les chiffres ont leur propre traitement typographique
  (tabular-nums, alignement à droite, codage couleur positif/négatif).
  L'interface s'adapte à deux modes (portefeuille N dossiers vs mono-entreprise)
  et au statut de chaque dossier, sans jamais afficher de fonctions grisées.
  Décision et alternatives écartées : docs/adr/ADR-008-design-system-monochrome.md
  Référence d'inspiration : docs/archive/DESIGN-revolut.md

colors:
  # --- Action : l'encre (le bouton principal est noir, jamais orange) ---
  primary: "#111111"
  primary-bright: "#2B2B2B"
  primary-deep: "#000000"
  primary-subtle: "#FFF8EA"
  on-primary: "#FFFFFF"

  # --- Accent (nommé signal pour ne pas entrer en collision avec --accent de shadcn) ---
  signal: "#C2410C"
  signal-deep: "#9A3412"
  # Surligneur (le jaune du CRM) et lavis des lignes « à traiter ».
  highlight: "#FDE7C4"
  highlight-wash: "#FFF8EA"

  # --- Neutres (chauds) ---
  ink: "#111111"
  body: "#3D3D3A"
  subtle: "#55534E"
  muted: "#66645F"
  # faint : éléments non textuels seulement (icônes, points), pas de texte.
  faint: "#A8A59E"
  on-dark: "#FBFAF8"
  on-dark-mute: "rgba(251,250,248,0.65)"

  # --- Canvas et surfaces ---
  canvas: "#FFFFFF"
  canvas-app: "#FBFAF8"
  surface-raised: "#FFFFFF"
  surface-soft: "#F4F2EE"
  surface-overlay: "#FFFFFF"
  surface-dark: "#111111"
  surface-dark-raised: "#2B2B2B"

  # --- Bordures ---
  border: "#E7E5E0"
  border-strong: "#D4D1CA"
  border-focus: "#C2410C"
  hairline: "#F0EEE9"

  # --- Sémantiques générales ---
  success: "#15803D"
  success-subtle: "#F0FDF4"
  success-border: "#86EFAC"
  warning: "#A16207"
  warning-subtle: "#FEF3C7"
  warning-border: "#FCD34D"
  # Texte posé sur pending-subtle (contraste 6,15), là où pending seul serait juste.
  pending-ink: "#854D0E"
  danger: "#BE123C"
  danger-subtle: "#FFF1F2"
  danger-border: "#FDA4AF"
  info: "#0369A1"
  info-subtle: "#F0F9FF"
  info-border: "#7DD3FC"

  # --- Sémantiques comptables ---
  amount-positive: "#15803D"
  amount-negative: "#BE123C"
  amount-neutral: "#111111"
  validated: "#15803D"
  validated-subtle: "#F0FDF4"
  pending: "#A16207"
  pending-subtle: "#FEF3C7"
  auto-rule: "#0369A1"
  auto-rule-subtle: "#F0F9FF"
  auto-ml: "#7C3AED"
  auto-ml-subtle: "#F5F3FF"
  auto-llm: "#9333EA"
  auto-llm-subtle: "#FAF5FF"
  alert-anomaly: "#BE123C"
  alert-anomaly-subtle: "#FFF1F2"
  missing: "#66645F"
  closed: "#3D3D3A"
  closed-subtle: "#F4F2EE"

typography:
  # --- Titre d'accueil : un seul par écran (« 3 dossiers à traiter. ») ---
  display-xl:
    fontFamily: Inter
    fontSize: 56px
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: -0.04em

  # --- Titres de pages et dashboard ---
  display-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 600
    lineHeight: 1.21
    letterSpacing: -0.02em
  display-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.27
    letterSpacing: -0.22px

  # --- Titres de sections et panneaux ---
  heading-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.3
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
    fontSize: 28px
    fontWeight: 600
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
  # overline : en-tête de liste ou de colonne, toujours en majuscules
  # (textTransform: uppercase est porté par le composant, ex. table-header).
  overline:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: 0.06em
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
  # sm : pastilles internes ; md : « contrôles » (boutons, champs).
  sm: 4px
  md: 6px
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
  # Aucune ombre sur les cartes (filets border). Les tokens ci-dessous ne
  # servent qu'aux menus, popovers et fenêtres.
  none: none
  xs: "0 1px 2px rgba(17,17,17,0.06)"
  sm: "0 1px 3px rgba(17,17,17,0.08), 0 1px 2px rgba(17,17,17,0.04)"
  md: "0 4px 6px -1px rgba(17,17,17,0.08), 0 2px 4px -2px rgba(17,17,17,0.04)"
  lg: "0 10px 15px -3px rgba(17,17,17,0.08), 0 4px 6px -4px rgba(17,17,17,0.04)"
  overlay: "0 20px 25px -5px rgba(17,17,17,0.10), 0 8px 10px -6px rgba(17,17,17,0.04)"
  # Anneaux de focus (signal) : collé au champ ou au bouton (avec bordure
  # signal), ou détaché du fond par 2 px (lien, icône, onglet), sur fond clair
  # ou sombre.
  focus: "0 0 0 3px rgba(194,65,12,0.45)"
  focus-detache: "0 0 0 2px #FFFFFF, 0 0 0 4px #C2410C"
  focus-detache-sombre: "0 0 0 2px #111111, 0 0 0 4px #C2410C"

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
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
    transition: "{transition.base}"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button-md}"
    border: "1px solid {colors.ink}"
    rounded: "{rounded.md}"
    padding: 6px 15px
    height: 36px
    hoverBackground: "{colors.surface-soft}"
    activeBackground: "{colors.border}"
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
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
    activeBackground: "{colors.border}"
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
    transition: "{transition.base}"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "#FFFFFF"
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: 7px 16px
    height: 36px
    # Survol = danger à 90 % d'opacité (`hover:bg-danger/90`), appui = 80 %.
    hoverBackground: "rgba(190,18,60,0.90)"
    activeBackground: "rgba(190,18,60,0.80)"
    transition: "{transition.base}"
  button-sm:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-sm}"
    rounded: "{rounded.md}"
    padding: 4px 12px
    height: 28px
    transition: "{transition.base}"
  button-sm-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.subtle}"
    typography: "{typography.button-sm}"
    rounded: "{rounded.md}"
    padding: 4px 10px
    height: 28px
    hoverBackground: "{colors.surface-soft}"
    transition: "{transition.base}"
  # Cible tactile du chauffeur (habillage mobile, AXE-692) : mêmes variantes,
  # 44 px de haut. Utilisé pleine largeur sur téléphone.
  button-lg:
    typography: "{typography.button-md}"
    rounded: "{rounded.md}"
    padding: 12px 16px
    height: 44px
    transition: "{transition.base}"
  # Tous les boutons : désactivé = opacité 50 %, sans pointeur ni hover.
  button-disabled:
    opacity: 0.5
    pointerEvents: none

  # --- Liens et surlignage ---
  # Lien d'action : signal, 600, souligné (2 px, décalé de 3 px). Jamais rouge.
  link-action:
    textColor: "{colors.signal}"
    typography: "{typography.heading-sm}"
    textDecoration: underline
    textDecorationThickness: 2px
    textUnderlineOffset: 3px
    hoverTextColor: "{colors.signal-deep}"
    transition: "{transition.fast}"
  # Surlignage jaune : au plus un par écran (le chiffre ou le mot qui compte
  # dans le titre).
  highlight:
    textColor: "{colors.ink}"
    background: "linear-gradient(transparent 62%, {colors.highlight} 62%)"

  # --- Champs de saisie ---
  text-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    placeholderColor: "{colors.muted}"
    typography: "{typography.body-md}"
    border: "1px solid {colors.border-strong}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 36px
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
    # Erreur : aria-invalid pose la bordure danger, même focalisé.
    errorBorder: "{colors.danger}"
    transition: "{transition.fast}"
  text-input-lg:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    placeholderColor: "{colors.muted}"
    typography: "{typography.body-lg}"
    border: "1px solid {colors.border-strong}"
    rounded: "{rounded.md}"
    padding: 10px 14px
    height: 44px
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
    # Erreur : aria-invalid pose la bordure danger, même focalisé.
    errorBorder: "{colors.danger}"
  select:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.md}"
    padding: 7px 12px
    height: 36px
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"
  # Champ et liste du chauffeur : 44 px, texte 16 px (en dessous, iOS zoome).
  select-lg:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-lg}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.md}"
    padding: 0 12px
    height: 44px
    focusBorder: "{colors.border-focus}"
    focusRing: "{shadow.focus}"

  # --- Cards et panneaux (aucune ombre : le filet border suffit) ---
  card:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.lg}"
    padding: 20px
    shadow: "{shadow.none}"
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
    shadow: "{shadow.none}"
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
  # Sélection : lavis + filet d'encre (le repère signal est réservé aux lignes à traiter).
  transaction-row-selected:
    backgroundColor: "{colors.primary-subtle}"
    borderLeft: "2px solid {colors.primary}"
    transition: "{transition.fast}"
  transaction-row-alert:
    backgroundColor: "{colors.danger-subtle}"
    borderLeft: "2px solid {colors.danger}"

  # --- Ligne de dossier « à traiter » (accueil gestionnaire) ---
  row-a-traiter:
    backgroundColor: "{colors.highlight-wash}"
    textColor: "{colors.ink}"
    borderLeft: "3px solid {colors.signal}"
    borderBottom: "1px solid {colors.border}"
    padding: 16px 20px
    nameTypography: "{typography.heading-md}"
    reasonTypography: "{typography.body-sm}"
    reasonColor: "{colors.body}"
    amountTypography: "{typography.amount-md}"
    amountAlign: right
    actionLink: "{components.link-action}"
    transition: "{transition.fast}"

  # --- Statut d'un dossier du portefeuille (point + libellé) ---
  # Vocabulaire propre aux dossiers : distinct des 8 badges d'écriture.
  statut-dossier:
    textColor: "{colors.ink}"
    fontSize: 13px
    fontWeight: 600
    dotSize: 8px
    dotRounded: "{rounded.full}"
    gap: 8px
  statut-dossier-a-traiter:
    dotColor: "{colors.signal}"
  statut-dossier-a-jour:
    dotColor: "{colors.success}"
  statut-dossier-sans-compte:
    dotColor: "{colors.faint}"
  statut-dossier-cloture:
    dotColor: "{colors.closed}"

  # --- Carte de revue (file de revue — écran principal) ---
  review-card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.lg}"
    padding: 24px
    shadow: "{shadow.none}"
  review-card-source-rule:
    accentColor: "{colors.auto-rule}"
    accentBackground: "{colors.auto-rule-subtle}"
  review-card-source-ml:
    accentColor: "{colors.auto-ml}"
    accentBackground: "{colors.auto-ml-subtle}"
  review-card-source-llm:
    accentColor: "{colors.auto-llm}"
    accentBackground: "{colors.auto-llm-subtle}"

  # --- Badges de statut d'écriture (vocabulaire unique du produit) ---
  badge-validated:
    backgroundColor: "{colors.validated-subtle}"
    textColor: "{colors.validated}"
    border: "1px solid {colors.success-border}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.full}"
    padding: 2px 10px
  badge-pending:
    backgroundColor: "{colors.pending-subtle}"
    textColor: "{colors.pending-ink}"
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
    typography: "{typography.overline}"
    borderBottom: "1px solid {colors.border}"
    height: 36px
    padding: 0 16px
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

  # --- Navigation : barre horizontale (remplace la sidebar, AXE-874) ---
  nav-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    borderBottom: "1px solid {colors.border}"
    height: 64px
    padding: 0 40px
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.label-md}"
    hoverTextColor: "{colors.ink}"
    transition: "{transition.base}"
  nav-item-active:
    textColor: "{colors.ink}"
    typography: "{typography.heading-sm}"
    borderBottom: "2px solid {colors.ink}"
  # Une action est attendue dans cette section : point de 7 px à droite du libellé.
  nav-item-alert:
    dotColor: "{colors.signal}"
    dotSize: 7px
    dotRounded: "{rounded.full}"
  # Zone de compte, à droite de la barre.
  nav-account:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-dark}"
    size: 32px
    rounded: "{rounded.full}"

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
    shadow: "{shadow.none}"
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
    border: "1px solid rgba(251,250,248,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.success}"
  toast-warning:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    border: "1px solid rgba(251,250,248,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.warning}"
  toast-error:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    border: "1px solid rgba(251,250,248,0.12)"
    rounded: "{rounded.md}"
    padding: 12px 16px
    shadow: "{shadow.lg}"
    accentColor: "{colors.danger}"

  # --- Modals ---
  modal-overlay:
    backgroundColor: "rgba(17,17,17,0.50)"
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

AxeLCompta adopte un **design monochrome** (design system v2.0, direction
« C2 », décidée dans l'[ADR-008](docs/adr/ADR-008-design-system-monochrome.md)).
Le fond de l'application est `{colors.canvas-app}` (`#FBFAF8`), un blanc cassé
chaud ; les cartes et surfaces en relief sont en `{colors.canvas}` (`#FFFFFF`),
cernées d'un filet `{colors.border}` et **sans ombre**. Le texte et le bouton
principal sont à l'**encre** `{colors.ink}` (`#111111`), un noir chaud : jamais
de noir pur `#000000` sur blanc pur.

Toute la couleur d'accent tient en trois éléments, tous orange :
`{colors.signal}` (`#C2410C`) pour les repères, les liens d'action et le
point d'alerte ; `{colors.highlight}` (`#FDE7C4`) pour le surligneur jaune ;
`{colors.highlight-wash}` (`#FFF8EA`) pour le fond des lignes « à traiter ».
Partout ailleurs : des neutres chauds. (Le design system 1.x reposait sur un
accent bleu ; l'ADR-008 le remplace.)

La navigation est une **barre horizontale** en haut de l'écran : il n'y a plus
de barre latérale, donc plus aucune zone sombre dans l'interface courante. Les
tokens `surface-dark` et `on-dark` ne servent plus qu'aux toasts de décision.
Le mode sombre global n'est pas prévu avant la phase 5.

## Couleurs

### Action : l'encre

- **Primary** (`{colors.primary}` — `#111111`) : l'encre. Bouton d'action
  principal, avatar du compte. **Le bouton principal est noir, jamais orange.**
- **Primary Bright** (`{colors.primary-bright}` — `#2B2B2B`) : survol.
- **Primary Deep** (`{colors.primary-deep}` — `#000000`) : appui.
- **Primary Subtle** (`{colors.primary-subtle}` — `#FFF8EA`) : fond d'une
  ligne sélectionnée, le « lavis ».
- **On Primary** (`{colors.on-primary}` — `#FFFFFF`) : texte sur l'encre.

### Accent : signal

Nommé `signal` (et non `accent`) pour ne pas entrer en collision avec
`--accent` de shadcn.

- **Signal** (`{colors.signal}` — `#C2410C`) : orange foncé. Liens d'action,
  repères (filet gauche des lignes à traiter), point d'alerte de la navigation,
  anneau et bordure de focus.
- **Signal Deep** (`{colors.signal-deep}` — `#9A3412`) : survol et appui.
- **Highlight** (`{colors.highlight}` — `#FDE7C4`) : le surligneur, le jaune
  du CRM (crm.axelproject.fr).
- **Highlight Wash** (`{colors.highlight-wash}` — `#FFF8EA`) : fond des lignes
  « à traiter ».

Règles d'emploi, sans exception :

- L'orange ne sert **jamais de fond de bouton**.
- **Au plus un surlignage jaune par écran** : le chiffre ou le mot qui compte
  dans le titre (« **3** dossiers à traiter. »).
- Le rouge n'apparaît **jamais sur un lien ou un bouton**, hors `button-danger`.

### Neutrals

Gamme neutre chaude, légèrement tirée vers le beige, cohérente avec le fond :

- `{colors.ink}` (`#111111`) : titres, texte principal.
- `{colors.body}` (`#3D3D3A`) : corps de texte long.
- `{colors.subtle}` (`#55534E`) : labels, métadonnées, en-têtes de colonnes.
- `{colors.muted}` (`#66645F`) : placeholders, texte désactivé, états vides,
  entrées de navigation au repos. Contraste 5,67 sur `canvas-app`.
- `{colors.faint}` (`#A8A59E`) : icônes d'état vide, points de statut.
  **Éléments non textuels seulement** : jamais pour du texte.

### Surfaces et bordures

- **Canvas App** (`{colors.canvas-app}` — `#FBFAF8`) : fond de l'application
  (body). Ne jamais poser du blanc pur sur blanc pur.
- **Canvas** (`{colors.canvas}` — `#FFFFFF`) : cartes, panneaux, tableaux,
  barre de navigation.
- **Surface Soft** (`{colors.surface-soft}` — `#F4F2EE`) : survols légers,
  pills de filtre.
- **Border** (`#E7E5E0`), **Border Strong** (`#D4D1CA`), **Hairline**
  (`#F0EEE9`) : filets. `border-focus` est le `signal`.

### Sémantiques générales

| Token | Hex | Sous-ton | Bordure |
|---|---|---|---|
| `{colors.success}` | `#15803D` | `#F0FDF4` | `#86EFAC` |
| `{colors.warning}` (= `pending`) | `#A16207` | `#FEF3C7` | `#FCD34D` |
| `{colors.danger}` | `#BE123C` | `#FFF1F2` | `#FDA4AF` |
| `{colors.info}` | `#0369A1` | `#F0F9FF` | `#7DD3FC` |

`{colors.pending-ink}` (`#854D0E`) est le texte posé sur `pending-subtle`
(contraste 6,15) : c'est lui, et non `pending`, qui colore le texte de
`badge-pending`.

**Pourquoi un rouge cramoisi et un or.** L'ancien rouge (`#D42626`, et
`#B42318` dans certains écrans) était à ΔE 14 de l'orange du signal, donc
confondu avec lui ; l'ancien ambre `#B45309` aussi. Le cramoisi `#BE123C` est à
ΔE 33 du signal, l'or `#A16207` à ΔE 30 : le signal (« une action est
attendue ») ne peut plus être pris pour une erreur ou pour une attente.

### Sémantiques comptables

Ces couleurs ont un sens métier précis — ne jamais les détourner :

| Token | Hex | Usage strict |
|---|---|---|
| `{colors.amount-positive}` | `#15803D` | Recettes, soldes créditeurs, montants positifs |
| `{colors.amount-negative}` | `#BE123C` | Charges, soldes débiteurs, montants négatifs |
| `{colors.amount-neutral}` | `#111111` | Montant sans connotation (formulaire, total) |
| `{colors.validated}` | `#15803D` | Badge « validé », écriture confirmée par un humain |
| `{colors.pending}` | `#A16207` | Badge « à valider », en attente de décision |
| `{colors.auto-rule}` | `#0369A1` | Catégorisé par une règle déterministe |
| `{colors.auto-ml}` | `#7C3AED` | Catégorisé par le modèle ML |
| `{colors.auto-llm}` | `#9333EA` | Catégorisé par le LLM |
| `{colors.alert-anomaly}` | `#BE123C` | Alerte anomalie / abus potentiel |
| `{colors.missing}` | `#66645F` | Justificatif manquant (neutre, non bloquant) |
| `{colors.closed}` | `#3D3D3A` | Exercice clôturé (lecture seule) |

### Contrastes mesurés (WCAG)

| Paire | Ratio |
|---|---|
| encre / fond (`ink` / `canvas-app`) | 18,10 |
| `body` / fond | 10,45 |
| `muted` / fond | 5,67 |
| `signal` / fond | 4,96 |
| `signal` / blanc | 5,18 |
| `signal` / lavis (`highlight-wash`) | 4,90 |
| `signal-deep` / fond | 7,00 |
| `danger` / fond | 6,03 |
| `success` / fond | 4,81 |
| `pending` / fond | 4,72 |
| `pending-ink` / `pending-subtle` | 6,15 |
| encre / `highlight` | 15,65 |
| blanc / encre | 18,88 |

## Typographie

Une seule famille : **Inter** (open-source, Google Fonts), pour tous les
usages. DM Sans a été essayée dans le navigateur et écartée : elle n'a pas de
chiffres tabulaires, indispensables aux montants. Fraunces (serif) a aussi été
écartée (voir ADR-008). Corps à weight 400, labels à 500, **titres et boutons à
600** (plus de 700).

### Règle des montants — invariant non négociable

Tout montant affiché dans l'interface **doit** utiliser un token
`{typography.amount-*}` qui inclut `fontVariantNumeric: tabular-nums`.
Cela garantit l'alignement vertical des colonnes de chiffres (les `1` et
les `9` occupent la même largeur). Ne jamais afficher un montant avec
`{typography.body-md}` — même en passant, même en dev.

Format monétaire français : `1 234,56 €` (espace fine insécable comme
séparateur de milliers, virgule décimale). Utiliser `Intl.NumberFormat`
avec `locale: 'fr-FR'`, `style: 'currency'`, `currency: 'EUR'`.

Montants alignés à droite. Montants négatifs : couleur `{colors.amount-negative}`,
signe moins toujours affiché, jamais de parenthèses. Montants positifs :
couleur `{colors.amount-positive}` dans un tableau de recettes,
`{colors.amount-neutral}` dans un formulaire de saisie neutre.

### Hiérarchie

| Token | Taille | Poids | Utilisation principale |
|---|---|---|---|
| `{typography.display-xl}` | 56px / 1,05 / 600 / -0.04em | Titre d'accueil, **un seul par écran** (« 3 dossiers à traiter. ») |
| `{typography.display-lg}` | 28px / 600 / -0.02em | Titre de page, dashboard principal |
| `{typography.display-md}` | 22px / 600 | Titre de section majeure |
| `{typography.heading-lg}` | 20px / 1,3 / 600 | Titre de panneau, modale |
| `{typography.heading-md}` | 16px / 600 | Sous-titre, en-tête de groupe, nom d'un dossier à traiter |
| `{typography.heading-sm}` | 14px / 600 | Label de champ, entrée de navigation active |
| `{typography.overline}` | 12px / 600 / +0.06em, majuscules | En-tête de liste ou de colonne |
| `{typography.body-lg}` | 16px / 400 | Texte explicatif long (rare) |
| `{typography.body-md}` | 14px / 400 | Texte courant, libellés de transaction |
| `{typography.body-sm}` | 13px / 400 | Notes, historique compact, raison d'un dossier à traiter |
| `{typography.amount-xl}` | 28px / 600 | Solde total du portefeuille |
| `{typography.amount-lg}` | 18px / 600 | Solde d'un dossier, total de période |
| `{typography.amount-md}` | 15px / 500 | Montant dans une ligne de tableau |
| `{typography.amount-sm}` | 13px / 500 | Montant secondaire, récapitulatif |
| `{typography.label-md}` | 14px / 500 | Libellé de formulaire, entrée de navigation |
| `{typography.button-md}` | 14px / 600 | Label de bouton standard |
| `{typography.caption}` | 12px / 400 | Date, source, métadonnée compacte |
| `{typography.code}` | 13px / 400 mono | Numéro de compte PCG, SIREN, IBAN |

## Layout

### Application shell

```
┌──────────────────────────────────────────────────────────────────┐
│  Barre de navigation (64px) · fond canvas · filet bas border     │
│  Logo · Entreprises ● · Invitations · Rappels · …   ⌘K · (AR)    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│            Zone de contenu principale                            │
│            fond canvas-app (#FBFAF8)                             │
│            padding de page : 40px                                │
│            largeur max : 1180px                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
   ● = nav-item-alert : une action est attendue dans cette section
   (AR) = zone de compte, avatar de 32px sur fond ink
```

En mode mono-entreprise, la barre reste présente mais la liste des dossiers
est supprimée : l'entrée racine mène directement au tableau de bord du dossier.

### Espacement

- **Padding de page** : 40px sur les quatre côtés (barre de navigation
  comprise : `padding: 0 40px`).
- **Gap entre cards** : `{spacing.lg}` (16px).
- **Padding interne card** : 20px standard, `{spacing.xl}` (24px) pour les
  modales et la review-card.
- **Hauteur de ligne de tableau** : 52px (`{components.table-row}`) — permet
  de voir le contenu sans rembourrage excessif sur un portefeuille de 200
  dossiers.

### Grille de contenu

- **Max-width** : 1180px sur la zone de contenu.
- **Tableaux** : pleine largeur de la zone de contenu.
- **Dashboard portefeuille** : grille 3 colonnes à ≥ 1024px, 2 à ≥ 768px, 1 en
  dessous.
- **File de revue** : colonne unique centrée, max-width 720px — concentration
  maximale.

## Élévation et profondeur

Le système n'utilise **aucune ombre sur les cartes** : la profondeur vient du
contraste entre le fond `canvas-app` et les surfaces `canvas`, séparées par un
filet `border`. Les ombres `shadow-*` ne servent qu'aux éléments flottants.

| Niveau | Traitement | Usage |
|---|---|---|
| 0 — fond app | `{colors.canvas-app}` sans ombre | Body, fond de page |
| 1 — surface | `{colors.canvas}` + bordure, **sans ombre** | Cards, tableaux |
| 2 — panneau flottant | `{colors.canvas}` + `{shadow.md}` + bordure | Menus déroulants, popovers |
| 3 — overlay | `{colors.canvas}` + `{shadow.overlay}` + bordure | Fenêtres (modales) |
| N — navigation | `{colors.canvas}` + filet bas `{colors.border}`, sans ombre | Barre de navigation |

Pas de gradient décoratif (le seul gradient est le surlignage `highlight`),
pas d'effet glassmorphism, pas de fond flouté.

## Formes

- `{rounded.full}` — badges, pills de filtre, points de statut, avatar.
- `{rounded.xl}` (16px) — fenêtres (modales).
- `{rounded.lg}` (12px) — cards, review-card.
- `{rounded.md}` (6px) — les « contrôles » : boutons, champs, menus déroulants, toasts.
- `{rounded.sm}` (4px) — pastilles internes.
- `{rounded.xs}` (4px) — chips internes, kbd, petits éléments.
- `{rounded.none}` — tableaux full-width, barre de navigation.

## Composants clés

### Boutons

**`button-primary`** — action principale de la page
- Fond encre (`{colors.primary}`), texte blanc, `rounded.md`, 36px de haut.
  Noir, jamais orange.
- Un seul par écran au maximum (parfois zéro — la file de revue fonctionne au
  clavier, les boutons sont secondaires).

**`button-secondary`** — action alternative
- Fond canvas, filet encre de 1px, texte ink. Toujours en accompagnement d'un
  `button-primary`, jamais seul sur un écran.

**`button-ghost`** — action tertiaire ou de navigation
- Transparent, texte `{colors.subtle}`, fond au hover. Pour les actions de
  moindre importance (« Annuler », actions inline sur une ligne de tableau).

**`button-danger`** — action destructive
- Fond `{colors.danger}` (`#BE123C`), réservé aux confirmations de suppression.
  Toujours dans une modale de confirmation, jamais directement accessible sur
  une liste. Seul endroit où le rouge est un fond de bouton.

**Tailles** — `default` (36 px, desktop), `sm` (28 px, actions inline),
`lg` (44 px, **toute action du chauffeur sur téléphone**, souvent pleine
largeur : `<Button size="lg" className="w-full">`). Désactivé : opacité
50 %, sans hover ni pointeur. Focus : anneau `signal` (`{shadow.focus}`,
3 px à 45 % d'opacité) accompagné d'une bordure `signal`. Appui : secondary
et ghost passent au filet `{colors.border}`, danger à 80 % d'opacité.

### Champs de saisie

Fond canvas, bordure `{colors.border-strong}`, texte ink, placeholder
`{colors.muted}`, `rounded.md`, 36 px de haut (`lg` : 44 px, formulaires pleine
page et chauffeur). Focus : bordure et anneau `signal`. Erreur : l'attribut
`aria-invalid` pose la bordure `{colors.danger}`, qui reste rouge même
focalisée, et le lecteur d'écran l'annonce. Champ de montant : la prop
`montant` d'`Input` applique `tabular-nums` et l'alignement à droite.

### Liens d'action et surlignage

**`link-action`** : `{colors.signal}`, poids 600, souligné (épaisseur 2px,
décalé de 3px) ; survol en `{colors.signal-deep}`. C'est la forme des appels à
l'action en ligne (« Instruire → »). Un lien n'est jamais rouge.

**`highlight`** : surlignage jaune posé sur le chiffre ou le mot qui compte
dans le titre, `linear-gradient(transparent 62%, {colors.highlight} 62%)`.
Au plus un par écran.

### Navigation

La navigation du gestionnaire est la barre `nav-bar` : 64px de haut, fond
`{colors.canvas}`, filet bas `{colors.border}`, padding `0 40px`.

- **`nav-item`** : 14px, poids 500, `{colors.muted}`.
- **`nav-item-active`** : poids 600, `{colors.ink}`, filet bas de 2px `ink`.
- **`nav-item-alert`** : point de 7px `{colors.signal}` à droite du libellé.
  Signifie qu'une action est attendue dans cette section ; le libellé et, dans
  la page, le texte de la ligne concernée disent laquelle (le point ne
  distingue jamais seul).
- **Zone de compte** à droite : avatar de 32px sur fond `ink`.

Sous 1024px (≤ 1023px), les entrées passent dans un bouton « Menu » qui ouvre
un tiroir ; la zone de compte reste visible.

### Ligne « à traiter » (`row-a-traiter`)

Ligne de l'accueil du gestionnaire pour un dossier qui attend une décision :

- fond `{colors.highlight-wash}`, repère gauche de 3px `{colors.signal}` ;
- nom du dossier en 16px / 600 (`heading-md`) ;
- raison en 13px `{colors.body}` (« 2 factures sans justificatif ») ;
- montant à droite (`amount-md`) ;
- lien d'action `signal`, souligné : « Instruire → ».

### Statut d'un dossier (`statut-dossier`)

Point de 8px + libellé de 13px / 600. Vocabulaire propre aux dossiers du
portefeuille, **distinct des 8 badges d'écriture** (ci-dessous), qui gardent
leur sens et ne changent que de couleur.

| État | Point |
|---|---|
| À traiter | `{colors.signal}` |
| À jour | `{colors.success}` |
| Sans compte | `{colors.faint}` |
| Clôturé | `{colors.closed}` |

### File de revue (`review-card`)

L'écran le plus utilisé du produit. Règles strictes :

- Une seule `review-card` visible à la fois, centrée, max-width 720px.
- La **source de la proposition** est visuellement distincte avec l'accent
  correspondant (`auto-rule` → bleu, `auto-ml` → violet, `auto-llm` → violet
  plus profond) — l'utilisateur sait en un coup d'œil pourquoi cette
  proposition a été faite.
- Les **raccourcis clavier** (`{components.kbd}`) sont affichés à côté de chaque
  action : `A` Accepter, `1-3` Alternatives, `R` Rechercher, `S` Passer,
  `J` Joindre.
- Montant affiché en `{typography.amount-lg}` avec la couleur appropriée.
- Jamais de spinner plein écran entre deux transactions — transition instantanée
  ou squelette léger.

### Tableaux comptables

Les tableaux sont le cœur de l'interface comptable. Règles :

- En-tête : `{components.table-header}` — fond `canvas-app`, texte `subtle`,
  `overline` (12px, 600, majuscules, +0.06em). Toujours fixe (sticky) sur les
  tableaux longs.
- Lignes : `{components.table-row}` — 52px de haut, hover `canvas-app`.
- Colonnes de montants : **toujours alignées à droite**, tabular-nums.
- Ligne de total : `{components.table-row-total}` — fond `canvas-app`, weight 600,
  bordure supérieure double.
- Virtualisation obligatoire (TanStack Virtual) au-delà de 100 lignes — le grand
  livre peut dépasser 10 000 lignes pour un dossier actif.

### Badges de statut d'écriture

Vocabulaire unique — un seul badge par objet à la fois. Ces 8 badges qualifient
une **écriture ou une transaction** ; l'état d'un **dossier** utilise
`statut-dossier`, jamais un badge.

| Badge | Quand |
|---|---|
| `badge-validated` | Écriture validée par un humain |
| `badge-pending` | Proposition en attente de décision (texte `pending-ink`) |
| `badge-auto-rule` | Catégorisé par règle déterministe |
| `badge-auto-ml` | Catégorisé par ML |
| `badge-auto-llm` | Catégorisé par LLM |
| `badge-alert` | Anomalie ouverte sur la transaction |
| `badge-missing` | Justificatif attendu mais absent (non bloquant) |
| `badge-closed` | Appartient à un exercice clôturé |

Ne jamais créer de badge ad hoc. Si un état manque, ouvrir une discussion sur
le vocabulaire avant d'ajouter un token.

### Espace chauffeur (mobile-first)

Depuis septembre (doc 19), le chauffeur a son propre espace : Activité, À
traiter, Exercice, Mon résultat, Ma TVA, Ma société, Compte, et la cloche.
C'est la partie mobile-first du produit ; le gestionnaire reste
desktop-first. Règles distinctes :

- Colonne unique, max-width 600 px, barre de navigation en bas (qui suit
  l'encoche et disparaît quand le clavier est ouvert).
- **Cibles tactiles de 44 px** : `button-lg`, `text-input-lg`, `select-lg`,
  liens en `min-h-11`. Champs en 16 px (sinon iOS zoome au focus).
- Une action principale par écran, en pleine largeur.
- Langage du chauffeur, pas de jargon : les termes imposés (liasse, FEC)
  restent derrière une aide (« ? »).
- Chaque état vide ou erreur propose une action (« Réessayer »,
  « Actualiser »).
- Ni la barre de navigation horizontale ni les tableaux du gestionnaire.

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
- Séparer les cards du fond par un filet `{colors.border}`, sans ombre. Réserver
  `{shadow.md}` et `{shadow.overlay}` aux menus, popovers et fenêtres.
- Tout état vide a une action — jamais de page blanche sans invitation.
- Transitions à 150ms (`{transition.base}`) maximum — l'interface doit sembler
  réactive, pas animée.

### Don't

- Ne pas introduire d'autre couleur d'accent que `signal` sans nouvel ADR.
  L'[ADR-008](docs/adr/ADR-008-design-system-monochrome.md) remplace la règle
  d'origine (un seul accent bleu, pas de deuxième couleur sans ADR) : l'accent
  est désormais l'orange foncé `signal`, et toute modification repasse par une
  mesure de contraste et de ΔE.
- Ne pas utiliser l'orange `signal` comme fond de bouton (le bouton principal
  est noir), ni plus d'un surlignage jaune par écran.
- Ne pas mettre de rouge sur un lien ou un bouton (hors `button-danger`).
- Ne pas laisser `signal` distinguer seul une information : toujours du texte
  avec le point ou la couleur (voir « Accessibilité »).
- Ne pas utiliser `{colors.amount-positive}` ou `{colors.amount-negative}` pour
  autre chose que des montants — la couleur verte ne signifie pas « succès » sur
  un bouton dans ce contexte.
- Ne pas utiliser `{colors.faint}` pour du texte.
- Ne pas afficher de pages grisées pour les fonctionnalités non applicables au
  statut du dossier. Si une feature n'existe pas pour ce dossier, ne pas la
  montrer.
- Ne pas utiliser de spinner plein écran. Toujours des squelettes.
- Ne pas écrire de messages d'erreur avec des codes techniques (`Error 500`,
  `ECONNREFUSED`). Toujours un message humain + une action de récupération.
- Ne pas qualifier une anomalie juridiquement dans l'UI (`fraude`, `abus`).
  Toujours `à justifier`, `hors profil`, `à instruire`.
- Ne pas poser d'ombre sur une card, ni de `box-shadow` au-delà de
  `{shadow.md}` hors fenêtres. Pas de `drop-shadow` décoratif.
- Ne pas mélanger Aeonik Pro, Geist, DM Sans, Fraunces ou toute autre font :
  Inter uniquement, pour tous les usages, dans toute l'app.

## Comportement responsive

L'espace gestionnaire est desktop-first. L'espace chauffeur est
mobile-first (voir « Espace chauffeur »).

| Breakpoint | Largeur | Changements principaux |
|---|---|---|
| Desktop XL | ≥ 1440px | Grille dashboard 3 colonnes, tableaux pleine largeur |
| Desktop | 1280–1439px | Idem, container légèrement réduit |
| Laptop | 1024–1279px | Barre de navigation complète ; grille dashboard 2 colonnes |
| Tablet | 768–1023px | Entrées de navigation dans un bouton « Menu » (tiroir) ; grille 1 colonne |
| Mobile | < 768px | Espace chauffeur (colonne unique, barre du bas) ; le gestionnaire n'est pas optimisé mobile |

À partir de 1023px et en dessous, les entrées de la barre de navigation
passent dans un bouton « Menu » qui ouvre un tiroir ; la zone de compte reste
visible.

L'espace chauffeur n'a pas de barre de navigation horizontale : navigation par
la barre du bas. Les textes juridiques (`/legal/…`) sont des pages publiques
sans barre de navigation.

## Accessibilité

- Contrastes WCAG AA obligatoires sur tous les textes. Vérifier avec Radix
  Colors ou Tailwind Contrast Checker avant tout nouveau token de couleur
  (les valeurs mesurées sont dans « Contrastes mesurés »).
- Focus ring visible sur tous les éléments interactifs : `{shadow.focus}`
  (anneau `signal` de 3 px à 45 % d'opacité, **avec une bordure `signal`**)
  sur un champ ou un bouton, `{shadow.focus-detache}` sur un lien ou une icône,
  et `{shadow.focus-detache-sombre}` sur fond sombre. Classes Tailwind :
  `focus-visible:shadow-focus`, `…-focus-detache`, `…-focus-detache-sombre`.
  Jamais de valeur `shadow-[…]` en dur.
- Navigation clavier complète — les professionnels vivent au clavier, notamment
  dans la file de revue.
- Touch targets minimum 44px sur les éléments mobiles (page de signature et habillage chauffeur). Les champs du chauffeur font 16px : en dessous, iOS zoome au focus. Aucun texte chauffeur sous 12px.
- Pas de couleur comme seul vecteur d'information : les montants négatifs ont
  la couleur ET le signe `-` ; les badges ont la couleur ET le texte.
  **`signal` ne distingue jamais seul : texte + point.** Le point d'une entrée
  de navigation ou d'un statut de dossier est toujours accompagné d'un libellé,
  et un lien d'action est souligné, pas seulement coloré.

## Correspondance Tailwind / shadcn-ui

Le projet utilise **Tailwind CSS v4** + shadcn/ui (migré depuis v3 le
2026-09-22 — le CLI shadcn actuel ne génère que du code v4). Les tokens
DESIGN.md vivent dans un bloc `@theme` (`frontend/app/globals.css`, valeurs
hex directes, pas de triplet RGB — Tailwind v4 n'en a plus besoin) : c'est
la source de vérité pour tout ce qui est spécifique au produit
(`--color-primary`, `--color-ink`, `--color-signal`, `--color-auto-ml`, etc.,
préfixe `--color-*` obligatoire en v4 pour que Tailwind génère les classes
`bg-*`/`text-*` correspondantes).

Les variables génériques shadcn (celles que les composants `ui/*` générés
par le CLI référencent — `--background`, `--foreground`, `--card`,
`--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`,
`--border`, `--input`, `--ring`) vivent dans un second bloc `:root`. Elles
**référencent désormais les tokens** (`var(--color-…)`) au lieu de dupliquer
des valeurs hex : changer un token suffit (le CLI génère par défaut une
palette grise neutre — toujours l'écraser, jamais la garder telle quelle) :

```css
:root {
  --background: var(--color-canvas-app);      /* #FBFAF8 */
  --foreground: var(--color-ink);             /* #111111 */
  --card: var(--color-canvas);                /* #FFFFFF */
  --primary: var(--color-primary);            /* l'encre, #111111 */
  --primary-foreground: var(--color-on-primary);
  --secondary: var(--color-canvas);           /* button-secondary */
  --muted: var(--color-surface-soft);
  --muted-foreground: var(--color-subtle);
  --accent: var(--color-highlight-wash);      /* lavis, #FFF8EA */
  --destructive: var(--color-danger);         /* #BE123C */
  --border: var(--color-border);
  --input: var(--color-border);               /* border, text-input */
  --ring: var(--color-signal);                /* #C2410C */
  --radius: 0.375rem;                         /* rounded.md, 6px */
}
```

Le `--accent` de shadcn est le lavis `highlight-wash` ; l'accent orange du
produit s'appelle `signal` pour éviter toute collision.

Piège vérifié en pratique : `shadcn init`/`add` propose **Geist** comme
police par défaut (preset Nova) — toujours l'écarter, `--font-sans` doit
rester Inter, branchée par `next/font/google` via la variable `--font-inter`,
sans exception.

Les ombres (`--shadow-xs` à `--shadow-overlay`) et les anneaux de focus
(`--shadow-focus*`) sont aussi dans `@theme` : ils **remplacent** les ombres
grises par défaut de Tailwind, et `shadow-xs`, `shadow-sm`… suivent donc ce
contrat. Les variables `--sidebar-*` du bloc `:root` viennent du CLI shadcn
et ne servent pas : la navigation est une barre horizontale écrite en classes
Tailwind.

Pour les montants, utiliser la classe utilitaire Tailwind `tabular-nums`
(`font-variant-numeric: tabular-nums`) et ne jamais oublier `text-right` sur
les colonnes numériques.

## Outils de référence

- **Décision de design** : [`docs/adr/ADR-008-design-system-monochrome.md`](docs/adr/ADR-008-design-system-monochrome.md)
  — palette, accent, police, navigation, alternatives écartées.
- **Inspiration design** : `docs/archive/DESIGN-revolut.md` — analyse du
  système marketing Revolut, utile pour comprendre la rigueur de tokenisation
  attendue. Ne pas copier les choix visuels (canvas noir, Aeonik Pro) — ils
  sont inadaptés au B2B comptable. Le CRM de l'équipe (crm.axelproject.fr) a
  inspiré le surligneur jaune et le ton du design v2.0.
- **Composants** : shadcn/ui comme point de départ, chaque composant personnalisé
  avec les tokens ci-dessus.
- **Storybook** : catalogue vivant du design system — à alimenter en parallèle
  du front (phase 1, tâche 1.4).
- **Validation** : `npx @google/design.md lint DESIGN.md` pour détecter les
  tokens orphelins.

## Known Gaps

- **Design system v2.0 (2026-11-11)** : tokens, DESIGN.md et ADR-008 faits ;
  composants Button/Input/Card/Badge faits (AXE-875), primitives Select/Dialogue/
  Toast/Tableau (AXE-876), navigation (AXE-877) à faire. Tant que ces tickets
  ne sont pas livrés, les composants du code peuvent encore refléter l'ancien
  rendu (bleu, sidebar, ombres) : le contrat est DESIGN.md.
- **Remise à jour du 2026-11-10 (AXE-870)** (historique) : code et contrat
  relus l'un contre l'autre. Les couleurs étaient déjà identiques (53 tokens).
  Écarts corrigés : ombres du contrat absentes du code (Tailwind utilisait ses
  ombres grises) → ajoutées à `@theme` ; anneau de focus à 45 % dans le
  code mais 12 % ici → le contrat suit le code, et 18 valeurs
  `shadow-[…]` en dur deviennent des tokens ; texte indicatif des champs
  en `subtle` (le contrat disait `muted`) ; taille 44 px du chauffeur
  utilisée partout (`h-11`) mais absente → `button-lg` (et `size="lg"` sur
  `Button`), `select-lg` ; page de signature → espace chauffeur ;
  `surface-raised` et `surface-overlay` ajoutés au code ; une classe de
  palette Tailwind brute (écran d'import) remplacée par les tokens. Les
  écrans qui forcent `h-11` sur un `Button` peuvent passer à `size="lg"` au
  fil de l'eau : même rendu.
- Pas de composant `Select` : les listes déroulantes du chauffeur sont des
  `<select>` en classes Tailwind qui suivent `select-lg`. À extraire en
  composant avec les primitives de AXE-876.
- **V1 des composants faite (2026-09-22)** (historique), via shadcn/ui (Radix +
  CVA) — a nécessité de migrer le projet **Tailwind v3 → v4** au passage (le CLI
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
  `Input uiSize="lg"` + `Button`). Plus aucun écran du produit n'a de bouton,
  carte ou champ de saisie en classes Tailwind ad hoc. La passe UX/UI
  proprement dite (revue visuelle, pas juste la conformité aux tokens) est
  reprise par la refonte AXE-873. `review-card`, `table-*`, `toast-*`,
  `modal` restent des tokens DESIGN.md sans composant React, aucun écran
  actuel n'en a besoin pour l'instant.
- ~~Parcours chauffeur : problème plus profond que le design system~~
  (2026-09-22) — traité depuis : espace chauffeur en écrans séparés, une
  opération à la fois, revues UX AXE-563 et AXE-704 (novembre).
- Thème sombre (dark mode global) — prévu en phase 5. Les tokens
  `surface-dark` et `on-dark` ne servent qu'aux toasts, ce n'est pas un dark
  mode.
- États disabled : documentés le 2026-11-10 (`button-disabled`, opacité 50 %).
- Design system Figma — les maquettes des 3 écrans clés (doc 12, tâche 0.3)
  doivent utiliser ces tokens comme source de vérité, pas l'inverse.
- Animations et micro-interactions au-delà des transitions de base — hors scope
  V1.
