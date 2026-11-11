import * as React from "react"
import { cn } from "cn"

/** DESIGN.md § Champs de saisie › `text-input` (36px) — `uiSize="lg"` pour
 * `text-input-lg` (44px, formulaires pleine page comme la connexion).
 * Nommé `uiSize`, pas `size` : `size` est déjà l'attribut HTML natif de
 * `<input>` (largeur en caractères), un type différent (`number`).
 *
 * `montant` : règle des montants de DESIGN.md (chiffres tabulaires, alignés à
 * droite) pour que les colonnes de saisie se lisent d'un coup d'œil.
 *
 * Erreur : pilotée par `aria-invalid`, pas par une prop de plus. Le lecteur
 * d'écran l'annonce, et le style suit sans que l'écran ait à le redire. */
function Input({
  className,
  type,
  uiSize = "default",
  montant = false,
  ...props
}: React.ComponentProps<"input"> & { uiSize?: "default" | "lg"; montant?: boolean }) {
  return (
    <input
      type={type}
      data-slot="input"
      data-size={uiSize}
      className={cn(
        "w-full min-w-0 rounded-md border border-border-strong bg-canvas text-ink outline-none transition-colors duration-100 placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-border-focus focus-visible:shadow-focus",
        // Après le focus : en erreur, la bordure reste rouge même focalisée
        // (l'anneau `shadow-focus` signale seul le focus).
        "aria-invalid:border-danger",
        uiSize === "lg" ? "h-11 px-3.5 text-base" : "h-9 px-3 text-sm",
        montant && "tabular-nums text-right",
        className
      )}
      {...props}
    />
  )
}

export { Input }
