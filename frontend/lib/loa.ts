/** AXE-803 : contrats de LOA du chauffeur. */

export type ContratLoaEntree = {
  loueur: string;
  vehicule: string;
  debut: string;
  duree_mois: number;
  loyer_mensuel_cts: number;
  premier_loyer_cts: number;
  prix_levee_cts: number;
  co2_g_km?: number | null;
};

export type ContratLoaVue = ContratLoaEntree & {
  id: string;
  terme: string;
  charge_premier_loyer_exercice_cts: number;
  cca_fin_exercice_cts: number;
  engagement_restant_cts: number;
};

/** Une durée en mois saisie par le chauffeur, bornée comme côté serveur. */
export function lireDureeMois(saisie: string): number | null {
  const mois = Number(saisie.trim());
  if (!Number.isInteger(mois) || mois < 6 || mois > 120) return null;
  return mois;
}

/** Ce qu'il reste à payer, dit simplement. */
export function phraseEngagement(restantCts: number): string {
  return restantCts > 0 ? "Reste à payer jusqu'à la fin du contrat, option comprise" : "Contrat terminé";
}
