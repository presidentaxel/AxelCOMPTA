/** Retrait d'espèces (AXE-844) : une question dédiée au lieu de la liste de
 * catégories. Les codes sont ceux de l'API. */

export const CATEGORIE_RETRAIT = "retrait_especes";
export const REPONSE_PERSONNELLE = "usage_personnel";
export const REPONSE_NE_SAIT_PLUS = "a_preciser_expert";

/** Ce qu'un chauffeur paie le plus souvent en espèces pour son activité. */
export const CATEGORIES_ACTIVITE_ESPECES = [
  "carburant",
  "peage_stationnement",
  "repas_et_receptions",
  "entretien_reparation_vehicule",
] as const;

export function estRetrait(proposition: string | null | undefined): boolean {
  return proposition === CATEGORIE_RETRAIT;
}

/** La phrase après la réponse, ou `null` s'il n'y a rien à ajouter. */
export function suiteDeLaReponse(categorie: string): string | null {
  if (categorie === REPONSE_PERSONNELLE) return null;
  if (categorie === REPONSE_NE_SAIT_PLUS) return "Votre comptable s'en occupe.";
  return "Ajoutez le ticket en photo : sans lui, la dépense ne peut pas être gardée.";
}
