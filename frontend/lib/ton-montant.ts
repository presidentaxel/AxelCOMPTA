/** Couleur d'un montant (DESIGN.md › Sémantiques comptables). Le signe moins
 * est toujours écrit par `formatMontant` : la couleur s'y ajoute, elle ne le
 * remplace jamais. */
export type TonMontant = "negatif" | "positif" | "neutre";

/** `signe` : une opération, rouge si elle sort, vert si elle entre.
 * `neutre` : un total ou un récapitulatif sans connotation (retenues, solde),
 * seulement rouge s'il est négatif. Zéro n'est jamais coloré. */
export type ModeTon = "signe" | "neutre";

export function tonMontant(centimes: number, mode: ModeTon): TonMontant {
  if (centimes < 0) return "negatif";
  if (centimes > 0 && mode === "signe") return "positif";
  return "neutre";
}
