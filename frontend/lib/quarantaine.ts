import type { EntreeQuarantaine } from "./types";

/** Les entrées encore à traiter d'abord, puis celles déjà traitées (AXE-424). */
export function trierQuarantaine(entrees: EntreeQuarantaine[]): EntreeQuarantaine[] {
  return [...entrees].sort((a, b) => Number(a.decision !== null) - Number(b.decision !== null));
}

/** Ce qu'il reste à faire, pour le titre du bloc. */
export function resteATraiter(entrees: EntreeQuarantaine[]): number {
  return entrees.filter((entree) => entree.decision === null).length;
}

/** « Acceptée par x le … » ou « Ignorée par x le … ». */
export function phraseResolution(entree: EntreeQuarantaine, date: (iso: string) => string): string | null {
  if (entree.decision === null || entree.resolue_le === null) return null;
  const verbe = entree.decision === "accepter" ? "Acceptée" : "Ignorée";
  return `${verbe} par ${entree.resolue_par ?? "un membre"} le ${date(entree.resolue_le)}`;
}
