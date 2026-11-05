/** Étapes de l'écran Exercice, dans l'ordre : provisions, clôture, documents,
 * greffe, affectation. Une étape suivante reste inactive tant que la
 * précédente n'est pas faite, et dit pourquoi. */

export function phraseOperationsRestantes(nombre: number): string {
  const mot = nombre > 1 ? "opérations" : "opération";
  return `Il reste ${nombre} ${mot} à traiter.`;
}

/** Pourquoi documents, greffe et affectation attendent.
 * `null` : la clôture est faite et plus aucune opération n'est à trancher. */
export function raisonApresCloture(
  operationsRestantes: number,
  comptesClos: boolean,
): string | null {
  if (operationsRestantes > 0) {
    return phraseOperationsRestantes(operationsRestantes);
  }
  if (!comptesClos) {
    return "Les comptes ne sont pas clôturés.";
  }
  return null;
}
