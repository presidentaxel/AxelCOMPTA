/** AXE-831 : la TVA d'une dépense commence par l'estimation de la table
 * versionnée. Un montant lu plus tard sur un justificatif la remplace :
 * ce n'est plus une estimation. */

import { formatMontant } from "./format";

/** Au-delà de ce montant (en centimes), l'écart possible vaut un ticket. */
export const SEUIL_TICKET_CTS = 150_00;

export function phraseTva(
  tvaEstimeeCts: number | null | undefined,
  tvaReleveeCts: number | null | undefined,
  montantCts: number,
  demanderTicket: boolean,
): string | null {
  if (tvaReleveeCts) return `TVA : ${formatMontant(tvaReleveeCts)}.`;
  if (!tvaEstimeeCts) return null;
  const phrase = `Dont TVA estimée : ${formatMontant(tvaEstimeeCts)}.`;
  if (!demanderTicket || Math.abs(montantCts) < SEUIL_TICKET_CTS) return phrase;
  return `${phrase} Joignez le ticket pour la confirmer.`;
}
