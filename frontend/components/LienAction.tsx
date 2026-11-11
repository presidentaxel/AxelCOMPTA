import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "cn";

/** Lien d'action de DESIGN.md (`link-action`) : signal, 600, souligné de 2 px
 * décalé de 3 px. 44 px de haut, car ces liens se touchent au doigt ; l'anneau
 * détaché reste visible sur le fond crème comme sur la carte blanche. */
const CLASSE =
  "inline-flex min-h-11 items-center rounded-sm text-left text-sm font-semibold text-signal underline decoration-2 underline-offset-[3px] outline-none transition-colors duration-100 hover:text-signal-deep focus-visible:shadow-focus-detache";

/** Lien vers une autre page. */
export function LienAction({ className, ...props }: ComponentProps<typeof Link>) {
  return <Link className={cn(CLASSE, className)} {...props} />;
}

/** Même rendu pour une action qui ne change pas de page (un `<button>`,
 * pas un faux lien). */
export function BoutonLien({ className, type = "button", ...props }: ComponentProps<"button">) {
  return <button type={type} className={cn(CLASSE, className)} {...props} />;
}
