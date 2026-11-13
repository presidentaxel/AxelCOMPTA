/** Même forme que `BudgetLlm` (types), sans l'importer : ce fichier est
 * compilé seul pour les tests unitaires. */
type Budget = { depense_usd: number; plafond_usd: number };

const DOLLARS = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "USD" });

/** AXE-887 : « L'IA propose une catégorie quand ni règle ni modèle ne
 * suffisent. Ce mois-ci : 1,20 $ US sur 5,00 $ US. » */
export function resumeBudgetLlm(budget: Budget): string {
  const depense = DOLLARS.format(budget.depense_usd);
  const plafond = DOLLARS.format(budget.plafond_usd);
  return `L'IA propose une catégorie quand ni règle ni modèle ne suffisent. Ce mois-ci : ${depense} sur ${plafond}.`;
}
