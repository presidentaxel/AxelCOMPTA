import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "cn";

/** DESIGN.md § Liens d'action : `signal`, poids 600, souligné (2 px, décalé de
 * 3 px), `signal-deep` au survol. Le soulignement porte le sens avec la couleur
 * (`signal` ne distingue jamais seul). 44 px de haut : ces liens se touchent au
 * doigt ; l'anneau détaché reste visible sur le fond crème comme sur la carte
 * blanche. Exportée pour qu'un vrai `<button>` (action sans navigation) porte
 * exactement la même forme qu'un lien. */
export const CLASSES_LIEN_ACTION =
  "inline-flex min-h-11 items-center rounded-sm text-left text-sm font-semibold text-signal underline decoration-2 underline-offset-[3px] outline-none transition-colors duration-100 hover:text-signal-deep focus-visible:shadow-focus-detache disabled:pointer-events-none disabled:opacity-50";

/** Lien vers une autre page. */
export function LienAction({ className, ...props }: ComponentProps<typeof Link>) {
  return <Link className={cn(CLASSES_LIEN_ACTION, className)} {...props} />;
}

/** Même rendu pour une action qui ne change pas de page (un `<button>`,
 * pas un faux lien). */
export function BoutonLien({ className, type = "button", ...props }: ComponentProps<"button">) {
  return <button type={type} className={cn(CLASSES_LIEN_ACTION, className)} {...props} />;
}
