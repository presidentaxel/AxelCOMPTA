import * as React from "react"
import { cn } from "cn"

/** DESIGN.md § Tableaux comptables. Le tableau est en `border-separate` et non
 * en `border-collapse` : avec des bordures fusionnées, le filet de l'en-tête
 * fixe resterait en haut du tableau au défilement au lieu de suivre l'en-tête.
 * Les filets sont donc posés sur les cellules, pas sur les lignes.
 *
 * Le conteneur défile (`overflow-auto`) : un en-tête `sticky` se fige dans CE
 * conteneur. Pour le figer pendant le défilement d'un tableau long, bornez sa
 * hauteur par `className` (par exemple `max-h-[70vh]`).
 *
 * Au-delà de 100 lignes, DESIGN.md impose la virtualisation : ce composant ne
 * la fait pas. */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className={cn("relative w-full overflow-auto", className)}>
      <table
        data-slot="table"
        className="w-full border-separate border-spacing-0 text-sm text-ink"
        {...props}
      />
    </div>
  )
}

/** `sticky` fige les cellules d'en-tête (pas le `<thead>`, moins fiable selon
 * les navigateurs), au-dessus des lignes qui défilent dessous. */
function TableHeader({
  className,
  sticky = false,
  ...props
}: React.ComponentProps<"thead"> & { sticky?: boolean }) {
  return (
    <thead
      data-slot="table-header"
      className={cn(sticky && "[&_th]:sticky [&_th]:top-0 [&_th]:z-10", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={className} {...props} />
}

/** Ligne de total : poids 600, fond `canvas-app`, bordure haute double. Les
 * bordures de `<tfoot>` ne s'affichent pas en `border-separate` : elle est
 * posée sur les cellules. Leur filet bas est retiré : le total ferme le
 * tableau. */
function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "bg-canvas-app font-semibold [&>tr]:h-11 [&>tr>td]:border-t-4 [&>tr>td]:border-b-0 [&>tr>td]:border-double [&>tr>td]:border-border-strong",
        className
      )}
      {...props}
    />
  )
}

/** 52px de haut, survol `surface-soft` (DESIGN.md › `table-row`). */
function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "h-13 transition-colors duration-100 hover:bg-surface-soft motion-reduce:transition-none",
        className
      )}
      {...props}
    />
  )
}

/** `montant` : colonne de montants, alignée à droite (règle des montants,
 * DESIGN.md › Typographie). À mettre sur l'en-tête comme sur les cellules. */
type ColonneMontant = { montant?: boolean }

/** En-tête `overline` : 12px, 600, majuscules, +0.06em, fond `canvas-app`,
 * filet bas `ink`. Le fond est sur chaque cellule pour masquer les lignes qui
 * passent dessous quand l'en-tête est fixe. */
function TableHead({
  className,
  montant = false,
  ...props
}: React.ComponentProps<"th"> & ColonneMontant) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-9 border-b border-ink bg-canvas-app px-4 align-middle text-xs font-semibold tracking-[0.06em] whitespace-nowrap text-subtle uppercase",
        montant ? "text-right" : "text-left",
        className
      )}
      {...props}
    />
  )
}

function TableCell({
  className,
  montant = false,
  ...props
}: React.ComponentProps<"td"> & ColonneMontant) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "border-b border-hairline px-4 align-middle",
        montant && "text-right tabular-nums",
        className
      )}
      {...props}
    />
  )
}

export { Table, TableHeader, TableBody, TableFooter, TableRow, TableHead, TableCell }
