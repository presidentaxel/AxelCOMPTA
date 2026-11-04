import type { SujetExpert } from "@/lib/types";

/** Met à jour les sujets d'un seul dossier, sans toucher aux autres. Les
 * nouveaux prennent la place des anciens (celle du premier), pour que la
 * liste ne saute pas sous les yeux de l'expert. */
export function remplacerSujetsDuDossier(
  sujets: SujetExpert[],
  dossierId: string,
  nouveaux: SujetExpert[],
): SujetExpert[] {
  const position = sujets.findIndex((sujet) => sujet.dossier_id === dossierId);
  const autres = sujets.filter((sujet) => sujet.dossier_id !== dossierId);
  if (position < 0) return [...autres, ...nouveaux];
  // Avant le premier ancien, il n'y a que des sujets d'autres dossiers.
  return [...autres.slice(0, position), ...nouveaux, ...autres.slice(position)];
}
