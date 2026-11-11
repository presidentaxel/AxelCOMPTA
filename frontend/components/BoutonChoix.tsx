import type { ReactNode } from "react";

/** Pastille de choix à état pressé (`aria-pressed`) : un canal, un
 * déclencheur, une portée. Actif : lavis `primary-subtle` et filet d'encre,
 * texte à l'encre (l'orange est réservé aux liens d'action). L'état ne tient
 * pas à la couleur seule : le filet passe de `border-strong` à `ink`. 36 px de
 * haut. Le focus reprend l'anneau des champs. */
export function BoutonChoix({
  actif,
  onClick,
  disabled = false,
  children,
}: {
  actif: boolean;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={actif}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex min-h-9 items-center rounded-full border px-4 text-sm font-semibold outline-none transition-colors duration-150 focus-visible:border-border-focus focus-visible:shadow-focus disabled:cursor-not-allowed disabled:opacity-50 ${
        actif
          ? "border-ink bg-primary-subtle text-ink"
          : "border-border-strong bg-canvas text-subtle hover:bg-surface-soft hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
