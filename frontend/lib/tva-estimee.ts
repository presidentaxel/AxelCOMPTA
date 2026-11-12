/** AXE-831 : la TVA déductible d'une dépense est estimée d'après sa
 * catégorie quand aucun ticket n'est joint. Le chauffeur le voit, et pour une
 * grosse dépense on l'invite à joindre le ticket qui la confirmera. */

/** Au-delà de ce montant (en centimes), l'écart possible vaut un ticket. */
export const SEUIL_TICKET_CTS = 150_00;

const FORMATEUR = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });

export function phraseTvaEstimee(
  tvaEstimeeCts: number | null | undefined,
  montantCts: number,
  aJustificatif: boolean,
): string | null {
  if (!tvaEstimeeCts || aJustificatif) return null;
  const phrase = `Dont TVA estimée : ${FORMATEUR.format(tvaEstimeeCts / 100)}.`;
  if (Math.abs(montantCts) < SEUIL_TICKET_CTS) return phrase;
  return `${phrase} Joignez le ticket pour la confirmer.`;
}
