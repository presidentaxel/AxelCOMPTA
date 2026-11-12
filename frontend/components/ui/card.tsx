import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

/** DESIGN.md § Cards et panneaux : `card` (défaut), `card-flat`, `card-section`,
 * `card-warning`/`card-danger`/`card-info`. Ne pas ajouter de variante hors
 * de cette liste sans mettre à jour DESIGN.md d'abord (même règle que les
 * badges). Aucune ombre sur une carte : le filet `border` suffit, les ombres
 * sont réservées aux menus et fenêtres (DESIGN.md › Élévation). */
const cardVariants = cva("text-ink", {
  variants: {
    variant: {
      default: "rounded-lg border border-border bg-canvas p-5",
      flat: "rounded-md bg-canvas-app p-4",
      section: "rounded-lg border border-border bg-canvas p-0",
      warning: "rounded-md border border-warning-border bg-warning-subtle px-4 py-3.5",
      danger: "rounded-md border border-danger-border bg-danger-subtle px-4 py-3.5",
      info: "rounded-md border border-info-border bg-info-subtle px-4 py-3.5",
    },
  },
  defaultVariants: {
    variant: "default",
  },
})

function Card({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof cardVariants>) {
  return (
    <div data-slot="card" className={cn(cardVariants({ variant, className }))} {...props} />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("mb-3 flex items-start justify-between gap-2", className)}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn("text-base font-semibold leading-snug text-ink", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card-description" className={cn("text-sm text-subtle", className)} {...props} />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-action" className={cn("shrink-0", className)} {...props} />
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn(className)} {...props} />
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("mt-4 flex items-center border-t border-border pt-4", className)}
      {...props}
    />
  )
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent }
