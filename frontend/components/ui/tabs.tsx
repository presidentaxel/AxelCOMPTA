import * as React from "react"
import { Tabs as TabsPrimitive } from "radix-ui"
import { cn } from "cn"

/** DESIGN.md § Navigation › `nav-item` / `nav-item-active`, appliqué aux
 * onglets d'une page : texte `muted`, onglet actif à l'encre avec un filet bas
 * de 2px `ink`, 14px, pas de fond. Radix fournit les rôles ARIA et le clavier
 * (flèches, Début/Fin). */
function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root data-slot="tabs" className={cn("flex flex-col gap-4", className)} {...props} />
}

function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("flex items-end gap-6 border-b border-border", className)}
      {...props}
    />
  )
}

/** Poids 600 partout, actif ou non : un poids qui change avec l'état
 * élargirait l'onglet et ferait sauter ses voisins. `-mb-px` fait recouvrir
 * le filet de la liste par le filet actif. L'anneau est détaché (DESIGN.md ›
 * Accessibilité) : un filet plat n'a pas de bordure à colorer. */
function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "-mb-px inline-flex h-10 items-center rounded-xs border-b-2 border-transparent text-sm font-semibold whitespace-nowrap text-muted outline-none transition-colors duration-150 motion-reduce:transition-none",
        "hover:text-ink data-[state=active]:border-ink data-[state=active]:text-ink",
        "focus-visible:shadow-focus-detache disabled:pointer-events-none disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("outline-none", className)}
      {...props}
    />
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
