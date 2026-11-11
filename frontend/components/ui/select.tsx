import { Select as SelectPrimitive } from "radix-ui"
import { Check, ChevronDown } from "lucide-react"
import { cn } from "cn"

export type SelectOption = { value: string; label: string }

/** DESIGN.md § Champs de saisie › `select` (36px) — `uiSize="lg"` pour
 * `select-lg` (44px, texte 16px : l'espace chauffeur, sinon iOS zoome au
 * focus). Même vocabulaire que `Input` : `uiSize`, jamais `size`.
 *
 * Il remplace le `<select>` natif, dont la liste ne se style pas. Radix fournit
 * le clavier (flèches, Début/Fin, saisie de la première lettre, Échap) et les
 * rôles ARIA. La liste est montée dans un portail, hors du conteneur
 * `.chauffeur` : la taille des options est donc posée ici, pas par le CSS
 * d'habillage du chauffeur.
 *
 * Radix interdit une option de valeur `""` : cette valeur sert à dire « rien
 * de choisi » et fait afficher le `placeholder`. Une option « Tous » d'un
 * filtre doit donc porter une valeur réelle (par exemple `"tous"`).
 *
 * Pour le `<label>` : soit `id` (le `<label htmlFor>` pointe le déclencheur),
 * soit `aria-label` quand il n'y a pas de libellé visible. */
function Select({
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  uiSize = "default",
  id,
  "aria-label": ariaLabel,
  className,
}: {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  uiSize?: "default" | "lg"
  id?: string
  "aria-label"?: string
  className?: string
}) {
  const lg = uiSize === "lg"
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        data-slot="select-trigger"
        data-size={uiSize}
        className={cn(
          "flex w-full min-w-0 items-center justify-between gap-2 rounded-md border border-border-strong bg-canvas text-left text-ink outline-none transition-colors duration-100 motion-reduce:transition-none data-placeholder:text-subtle disabled:cursor-not-allowed disabled:opacity-50",
          "focus-visible:border-border-focus focus-visible:shadow-focus",
          lg ? "h-11 px-3.5 text-base" : "h-9 px-3 text-sm",
          className
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} className="truncate" />
        <SelectPrimitive.Icon asChild>
          <ChevronDown aria-hidden="true" className="size-4 shrink-0 text-muted" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          data-slot="select-content"
          position="popper"
          sideOffset={4}
          className="z-50 max-h-(--radix-select-content-available-height) min-w-(--radix-select-trigger-width) overflow-hidden rounded-lg border border-border bg-canvas text-ink shadow-md"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                data-slot="select-item"
                className={cn(
                  "relative flex cursor-default items-center rounded-md py-2 pr-9 pl-3 outline-none select-none data-highlighted:bg-surface-soft",
                  lg ? "min-h-11 text-base" : "min-h-9 text-sm"
                )}
              >
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-3 flex items-center">
                  <Check aria-hidden="true" className="size-4" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}

export { Select }
