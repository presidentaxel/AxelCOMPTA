import type { ComponentProps } from "react";
import { cn } from "cn";

/** Titre d'une section d'écran : `heading-md` (16 px, 600), DESIGN.md ›
 * Hiérarchie. Les sections de l'exercice, des dividendes et de la paie
 * l'utilisent toutes : un seul gabarit plutôt que quatre variantes de
 * `text-sm font-medium`. */
export function TitreSection({ className, ...props }: ComponentProps<"h2">) {
  return <h2 className={cn("text-base font-semibold text-ink", className)} {...props} />;
}
