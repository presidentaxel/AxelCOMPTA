"use client";

import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "cn";

export type OptionRecherche = { value: string; label: string };

function sansAccent(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** Liste déroulante filtrable. La valeur vide affiche le placeholder :
 * une option « Toutes » porte une vraie valeur, comme le Select. */
function SelectRecherche({
  value,
  onValueChange,
  options,
  placeholder = "Choisir",
  "aria-label": ariaLabel,
  className,
}: {
  value: string;
  onValueChange: (value: string) => void;
  options: OptionRecherche[];
  placeholder?: string;
  "aria-label"?: string;
  className?: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const choisi = options.find((option) => option.value === value);
  const visibles = useMemo(() => {
    const jetons = sansAccent(saisie).split(/\s+/).filter(Boolean);
    if (jetons.length === 0) return options;
    return options.filter((option) => {
      const texte = sansAccent(`${option.label} ${option.value}`);
      return jetons.every((jeton) => texte.includes(jeton));
    });
  }, [options, saisie]);

  function choisir(suivant: string) {
    onValueChange(suivant);
    setOuvert(false);
    setSaisie("");
  }

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-expanded={ouvert}
        onClick={() => setOuvert((actuel) => !actuel)}
        className="flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded-md border border-border-strong bg-canvas px-3 text-left text-sm text-ink outline-none focus-visible:border-border-focus focus-visible:shadow-focus"
      >
        <span className={cn("truncate", !choisi && "text-subtle")}>{choisi?.label ?? placeholder}</span>
        <ChevronDown aria-hidden="true" className="size-4 shrink-0 text-muted" />
      </button>
      {ouvert && (
        <div className="absolute z-50 mt-1 w-full min-w-56 rounded-lg border border-border bg-canvas p-1 text-ink shadow-md">
          <input
            autoFocus
            value={saisie}
            onChange={(evenement) => setSaisie(evenement.target.value)}
            placeholder="Rechercher"
            aria-label={ariaLabel ? `Rechercher : ${ariaLabel}` : "Rechercher"}
            className="mb-1 h-9 w-full rounded-md border border-border-strong bg-canvas px-3 text-sm outline-none focus-visible:border-border-focus"
          />
          <ul className="max-h-60 overflow-auto">
            {visibles.map((option) => (
              <li key={option.value}>
                <button
                  type="button"
                  onClick={() => choisir(option.value)}
                  className="flex min-h-9 w-full items-center rounded-md px-3 text-left text-sm hover:bg-surface-soft"
                >
                  {option.label}
                </button>
              </li>
            ))}
            {visibles.length === 0 && <li className="px-3 py-2 text-sm text-subtle">Aucun résultat</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

export { SelectRecherche };
