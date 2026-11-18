/** AXE-969 : les comptes où l'expert peut imputer l'écart d'une semaine de
 * plateforme, selon son sens. Pur, testé avec `npm run test:unit`. */

export type CompteImputation = { value: string; label: string };

/** Choix « autre compte bancaire » : l'expert saisit le 512x. */
export const AUTRE_BANQUE = "512x";

const ENCORE_DU: CompteImputation[] = [
  { value: "658", label: "658 · petit écart de règlement (charge)" },
  { value: "455", label: "455 · versé sur un compte de l'associé" },
  { value: AUTRE_BANQUE, label: "512x · versé sur un autre compte du dossier" },
];

const TROP_VERSE: CompteImputation[] = [
  { value: "758", label: "758 · petit écart de règlement (produit)" },
  { value: "7068", label: "7068 · revenu hors course absent de Rollee (sans TVA)" },
  { value: "706", label: "706 · course absente de Rollee (avec TVA)" },
  { value: "455", label: "455 · à rendre à l'associé" },
  { value: AUTRE_BANQUE, label: "512x · autre compte du dossier" },
];

/** Écart positif : encore dû par la plateforme ; négatif : versé en trop. */
export function comptesImputation(ecartCts: number): CompteImputation[] {
  if (ecartCts === 0) return [];
  return ecartCts > 0 ? ENCORE_DU : TROP_VERSE;
}

export function sensEcart(ecartCts: number, plateforme: string): string {
  const nom = plateforme.charAt(0).toUpperCase() + plateforme.slice(1);
  if (ecartCts > 0) return `encore dus par ${nom}`;
  if (ecartCts < 0) return `versés en trop par ${nom}`;
  return "aucun écart";
}

/** Le compte à envoyer : le 512x saisi, ou le compte choisi. `null` si la
 * saisie n'est pas un sous-compte bancaire. */
export function compteAEnvoyer(choisi: string, saisi: string): string | null {
  if (choisi !== AUTRE_BANQUE) return choisi || null;
  const propre = saisi.trim();
  return /^512\d{1,5}$/.test(propre) ? propre : null;
}
