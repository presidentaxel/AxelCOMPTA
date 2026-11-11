import type { ComponentProps } from "react";
import { cn } from "cn";

/** Lien d'action (DESIGN.md › `link-action`) : signal, 600, souligné de 2 px
 * décalé de 3 px, plus profond au survol. Jamais rouge, et souligné pour que
 * l'orange ne soit pas le seul signe d'une action. À poser sur un lien
 * (`Link`, `<a>`) ; `BoutonLien` en est la forme pour une action qui ne
 * change pas de page. */
export const CLASSE_LIEN_ACTION =
  "rounded-sm text-sm font-semibold text-signal underline decoration-2 underline-offset-[3px] outline-none transition-colors duration-100 hover:text-signal-deep focus-visible:shadow-focus-detache motion-reduce:transition-none";

/** Un vrai `<button>` à l'allure d'un lien d'action. 36 px de haut au moins :
 * la cible reste facile à atteindre malgré l'absence de cadre. Désactivé, il
 * perd son soulignement et passe à 50 % comme tout bouton. */
export function BoutonLien({ className, type = "button", ...props }: ComponentProps<"button">) {
  return (
    <button
      type={type}
      className={cn(
        CLASSE_LIEN_ACTION,
        "inline-flex min-h-9 items-center text-left disabled:pointer-events-none disabled:no-underline disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
