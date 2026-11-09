/** Comment l'argent est sorti, dit en français (AXE-836). Les codes sont ceux
 * de la banque (`operation_type`, via Digifactory). Un code inconnu reste
 * affiché tel quel plutôt que caché. */
const LIBELLES: Record<string, string> = {
  card: "Payé par carte",
  transfer: "Virement",
  direct_debit: "Prélèvement",
  withdrawal: "Retrait d'espèces",
  check: "Chèque",
  deferred_card: "Carte à débit différé",
};

export function libelleMoyenPaiement(code: string | null): string | null {
  if (!code) return null;
  return LIBELLES[code] ?? code;
}
