import type { ReactNode } from "react";

/** `highlight` (DESIGN.md § Liens et surlignage) : le jaune du CRM sous le
 * mot qui compte. Au plus UN par écran, dans le titre d'accueil.
 *
 * Le dégradé est posé en style local : c'est une valeur de contrat
 * (`linear-gradient(transparent 62%, highlight 62%)`) qu'aucune classe Tailwind
 * n'exprime proprement. `box-decoration-break: clone` répète le surlignage sur
 * chaque ligne si le titre passe à la ligne. */
export function Surligneur({ children }: { children: ReactNode }) {
  return (
    <span
      className="text-ink"
      style={{
        background: "linear-gradient(transparent 62%, var(--color-highlight) 62%)",
        boxDecorationBreak: "clone",
        WebkitBoxDecorationBreak: "clone",
      }}
    >
      {children}
    </span>
  );
}
