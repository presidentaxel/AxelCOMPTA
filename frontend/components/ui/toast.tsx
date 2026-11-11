import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

/** DESIGN.md § Toasts : fond `surface-dark`, texte `on-dark`, filet clair
 * discret, et un accent de 3px à gauche qui dit le sens (`success`, `warning`,
 * `danger`). L'accent ne porte jamais le sens seul : le message le dit en
 * toutes lettres.
 *
 * Le composant ne se positionne pas : l'appelant le place (`className`). */
const toastVariants = cva(
  "rounded-md border border-on-dark/10 border-l-3 bg-surface-dark px-4 py-3 text-on-dark shadow-lg",
  {
    variants: {
      variant: {
        success: "border-l-success",
        warning: "border-l-warning",
        error: "border-l-danger",
      },
    },
    defaultVariants: {
      variant: "success",
    },
  }
)

type ToastVariant = NonNullable<VariantProps<typeof toastVariants>["variant"]>

/** `alert` pour l'erreur (lue tout de suite par les lecteurs d'écran),
 * `status` pour le reste (lu à la prochaine pause). */
function Toast({
  className,
  variant = "success",
  ...props
}: React.ComponentProps<"div"> & { variant?: ToastVariant }) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      data-slot="toast"
      data-variant={variant}
      className={cn(toastVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Toast }
export type { ToastVariant }
