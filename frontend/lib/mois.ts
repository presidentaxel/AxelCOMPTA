/** « 2026-01 » (valeur d'un champ mois) dit en français : « janvier 2026 ».
 * Une valeur illisible reste affichée telle quelle plutôt que cachée. */
const FORMATEUR_MOIS = new Intl.DateTimeFormat("fr-FR", {
  month: "long",
  year: "numeric",
  // Le 1er du mois à minuit UTC : sans fuseau fixe, l'ouest de Greenwich
  // afficherait le mois précédent.
  timeZone: "UTC",
});

export function libelleMois(valeur: string): string {
  const morceaux = /^(\d{4})-(0[1-9]|1[0-2])/.exec(valeur);
  if (morceaux === null) return valeur;
  return FORMATEUR_MOIS.format(new Date(Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, 1)));
}
