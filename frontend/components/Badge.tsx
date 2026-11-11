/** Vocabulaire de badge de statut, DESIGN.md § Badges de statut : 8 variantes,
 * une seule par objet à la fois. « Ne jamais créer de badge ad hoc. Si un état
 * manque, ouvrir une discussion sur le vocabulaire avant d'ajouter un token. »
 *
 * `neutral` est une exception délibérée, hors vocabulaire DESIGN.md : sert de
 * simple tag informatif (régime TVA, nom de plateforme) plutôt qu'un statut
 * d'écriture — usage différent, ne pas le confondre avec les 8 ci-dessus.
 */
export type BadgeVariant =
  | "validated"
  | "pending"
  | "auto-rule"
  | "auto-ml"
  | "auto-llm"
  | "alert"
  | "missing"
  | "closed"
  | "neutral";

const STYLES: Record<BadgeVariant, string> = {
  validated: "bg-validated-subtle text-validated border border-success-border",
  // `pending-ink` et non `pending` : l'or `pending` sur fond `pending-subtle`
  // tombe sous 4,5:1 ; `pending-ink` donne 6,15:1 (DESIGN.md › Contrastes).
  pending: "bg-pending-subtle text-pending-ink border border-warning-border",
  "auto-rule": "bg-auto-rule-subtle text-auto-rule border border-info-border",
  "auto-ml": "bg-auto-ml-subtle text-auto-ml border border-transparent",
  "auto-llm": "bg-auto-llm-subtle text-auto-llm border border-transparent",
  alert: "bg-alert-anomaly-subtle text-alert-anomaly border border-danger-border",
  missing: "bg-transparent text-muted border border-dashed border-border-strong",
  closed: "bg-closed-subtle text-closed border border-border",
  neutral: "bg-surface-soft text-subtle border border-border",
};

export function Badge({
  variant,
  children,
}: {
  variant: BadgeVariant;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[variant]}`}
    >
      {children}
    </span>
  );
}
