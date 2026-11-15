/** AXE-930 : un virement entre deux comptes (ou enveloppes) du chauffeur,
 * imputé au 580. Ce n'est ni un gain ni une charge. */
export const COMPTE_VIREMENT_INTERNE = "580";

export function estVirementInterne(operation: { compte: string }): boolean {
  return operation.compte === COMPTE_VIREMENT_INTERNE;
}

/** Les opérations du chauffeur, sans ses virements internes, et leur nombre. */
export function horsVirementsInternes<T extends { compte: string }>(
  operations: T[],
): { gardees: T[]; internes: number } {
  const gardees = operations.filter((operation) => !estVirementInterne(operation));
  return { gardees, internes: operations.length - gardees.length };
}

export function phraseVirementsInternes(internes: number): string | null {
  if (internes === 0) return null;
  return internes === 1
    ? "1 virement entre vos comptes n'est pas compté : ce n'est ni une recette ni une dépense."
    : `${internes} virements entre vos comptes ne sont pas comptés : ce ne sont ni des recettes ni des dépenses.`;
}
