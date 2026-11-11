// AXE-849 : ce que disent les registres officiels (INSEE, RNE) et les écarts
// avec la déclaration du dirigeant. Pur, testé.

export type EcartRegistre = { champ: string; declare: string; officiel: string; phrase: string };

export type RegistreVue = {
  siren: string | null;
  lu_le: string | null;
  sources: string[];
  forme_juridique: string | null;
  ecarts: EcartRegistre[];
};

const QUESTIONS: Record<string, string> = {
  etat: "Le registre indique que votre société est cessée.",
  forme_juridique: "Votre forme juridique",
  denomination: "Le nom de votre société",
  siege: "L'adresse de votre siège",
  capital: "Votre capital",
  dirigeant: "Le dirigeant",
};

/** Le titre d'un écart, pour le chauffeur. */
export function questionEcart(champ: string): string {
  return QUESTIONS[champ] ?? champ;
}

/** Une société cessée n'offre qu'un choix : la contester. */
export function peutRetenirRegistre(champ: string): boolean {
  return champ !== "etat";
}

/** Les écarts, la société cessée en premier. */
export function ecartsOrdonnes(ecarts: readonly EcartRegistre[]): EcartRegistre[] {
  return [...ecarts].sort((a, b) => Number(b.champ === "etat") - Number(a.champ === "etat"));
}
