import * as React from "react"
import { cn } from "cn"

/** DESIGN.md § Champs de saisie › `text-input` (36px) — `uiSize="lg"` pour
 * `text-input-lg` (44px, formulaires pleine page comme la connexion).
 * Nommé `uiSize`, pas `size` : `size` est déjà l'attribut HTML natif de
 * `<input>` (largeur en caractères), un type différent (`number`). */
function Input({
  className,
  type,
  uiSize = "default",
  ...props
}: React.ComponentProps<"input"> & { uiSize?: "default" | "lg" }) {
  return (
    <input
      type={type}
      data-slot="input"
      data-size={uiSize}
      className={cn(
        "w-full min-w-0 rounded-md border border-border bg-canvas text-ink outline-none transition-colors duration-100 placeholder:text-subtle disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-border-focus focus-visible:shadow-[0_0_0_3px_rgba(37,99,235,0.45)]",
        uiSize === "lg" ? "h-11 px-3.5 text-base" : "h-9 px-3 text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
