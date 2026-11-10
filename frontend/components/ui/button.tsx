import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

/** Implémente DESIGN.md § Composants clés › Boutons — 4 variantes, pas plus
 * (`primary`/`secondary`/`ghost`/`danger`), trois tailles (`default` = 36px/
 * button-md, `sm` = 28px/button-sm, `lg` = 44px/button-lg, cible tactile du
 * chauffeur). Un seul `button-primary` par écran au
 * maximum (règle DESIGN.md, pas imposée ici — au développeur de l'écran de
 * la respecter). */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap font-semibold transition-colors duration-150 ease-out outline-none disabled:pointer-events-none disabled:opacity-50 focus-visible:shadow-focus focus-visible:border-border-focus [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-on-primary hover:bg-primary-bright active:bg-primary-deep",
        secondary:
          "border border-border-strong bg-canvas text-ink hover:bg-canvas-app",
        ghost: "bg-transparent text-subtle hover:bg-surface-soft hover:text-ink",
        danger: "bg-danger text-on-primary hover:bg-danger/90",
      },
      size: {
        default: "h-9 rounded-md px-4 text-sm",
        sm: "h-7 rounded-sm px-3 text-[13px]",
        // button-lg : cible tactile de 44 px (habillage chauffeur, AXE-692).
        lg: "h-11 rounded-md px-4 text-sm",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
