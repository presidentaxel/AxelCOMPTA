// AXE-730 : ce que le chauffeur lit pour confirmer son entreprise. Pur, testé.

import type { ConfigurationDossier } from "./types";

const FORMES: Record<string, string> = {
  SASU: "SASU (vous êtes le seul associé)",
  SAS: "SAS (plusieurs associés)",
  EURL: "EURL (vous êtes le seul associé)",
  SARL: "SARL (plusieurs associés)",
  EI: "Entreprise individuelle",
};

const MANQUES: Record<string, string> = {
  siege: "l'adresse du siège",
  capital: "le capital",
  associes: "les associés",
};

export function libelleForme(code: string): string {
  return FORMES[code] ?? code;
}

/** Vrai quand le chauffeur a quelque chose à confirmer. */
export function aConfirmer(configuration: ConfigurationDossier): boolean {
  return configuration.a_confirmer.length > 0;
}

/** « Votre comptable doit encore renseigner le capital et les associés. »,
 * ou `null`. Ces éléments ne se confirment pas d'un clic. */
export function phraseIdentiteManquante(manques: readonly string[]): string | null {
  const noms = manques.map((code) => MANQUES[code]).filter((nom): nom is string => !!nom);
  if (noms.length === 0) return null;
  const liste = noms.length === 1 ? noms[0] : `${noms.slice(0, -1).join(", ")} et ${noms.at(-1)}`;
  return `Votre comptable doit encore renseigner ${liste} de la société.`;
}
