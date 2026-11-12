import { cn } from "cn";

import { formatMontant } from "@/lib/format";
import { tonMontant, type ModeTon, type TonMontant } from "@/lib/ton-montant";

const COULEUR: Record<TonMontant, string> = {
  negatif: "text-amount-negative",
  positif: "text-amount-positive",
  neutre: "text-amount-neutral",
};

/** Un montant, selon la règle de DESIGN.md › Typographie : chiffres
 * tabulaires, signe moins toujours écrit (jamais de parenthèses), rouge s'il
 * est négatif. L'alignement à droite est celui de la cellule ou de la ligne
 * qui le porte : ce composant n'impose pas de mise en page.
 *
 * `ton="signe"` (défaut) pour une opération : vert quand elle entre.
 * `ton="neutre"` pour un total ou un récapitulatif : seul le négatif se colore. */
export function Montant({
  centimes,
  ton = "signe",
  className,
}: {
  centimes: number;
  ton?: ModeTon;
  className?: string;
}) {
  return (
    <span className={cn("tabular-nums", COULEUR[tonMontant(centimes, ton)], className)}>
      {formatMontant(centimes)}
    </span>
  );
}
