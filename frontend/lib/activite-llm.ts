/** Même forme que l'activité LLM renvoyée par l'API, sans l'importer :
 * ce fichier est compilé seul pour les tests unitaires. */
type Activite = { libelles: number };

const NOMBRE = new Intl.NumberFormat("fr-FR");

function volume(libelles: number): string {
  if (libelles <= 0) return "aucun libellé";
  if (libelles === 1) return "1 libellé";
  return `${NOMBRE.format(libelles)} libellés`;
}

/** AXE-887 : « L'IA propose une catégorie quand ni règle ni modèle ne
 * suffisent. Ce mois-ci : 12 libellés. » Jamais le coût. */
export function resumeActiviteLlm(activite: Activite): string {
  return `L'IA propose une catégorie quand ni règle ni modèle ne suffisent. Ce mois-ci : ${volume(activite.libelles)}.`;
}
