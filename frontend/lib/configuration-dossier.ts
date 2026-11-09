// AXE-834 : ce que le gestionnaire lit quand la configuration d'une
// entreprise a été proposée sans certitude (Sirene). Pur, testé.

const NOMS: Record<string, string> = {
  forme_juridique: "forme juridique",
  exercice: "premier exercice",
};

/** « Forme juridique et premier exercice à confirmer par le dirigeant. »,
 * ou `null` s'il n'y a rien à confirmer. Un code inconnu n'est pas affiché. */
export function phraseAConfirmer(aConfirmer: readonly string[]): string | null {
  const noms = aConfirmer
    .map((code) => NOMS[code])
    .filter((nom): nom is string => !!nom);
  if (noms.length === 0) return null;
  const liste =
    noms.length === 1
      ? noms[0]
      : `${noms.slice(0, -1).join(", ")} et ${noms.at(-1)}`;
  return `${liste.charAt(0).toUpperCase()}${liste.slice(1)} à confirmer par le dirigeant.`;
}
