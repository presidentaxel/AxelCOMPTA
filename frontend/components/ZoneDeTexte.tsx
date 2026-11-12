import type { ComponentProps } from "react";
import { cn } from "cn";

/** Champ de texte sur plusieurs lignes, au gabarit d'`Input` (DESIGN.md ›
 * `text-input`) : filet `border-strong`, focus `signal`, et la bordure
 * `danger` quand `aria-invalid` est posé, même focalisé. */
export function ZoneDeTexte({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 rounded-md border border-border-strong bg-canvas px-3 py-2 text-sm text-ink outline-none transition-colors duration-100 placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-border-focus focus-visible:shadow-focus",
        "aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}
