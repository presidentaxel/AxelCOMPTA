// AXE-832 : présentation des comptes bancaires du chauffeur. Pur, sans
// React ni réseau, pour être testé avec `npm run test:unit`.

export type CompteAffiche = {
  compte: string;
  nom: string | null;
  solde_comptable_cts: number;
  solde_banque_cts: number | null;
  ecart_cts: number | null;
};

export type Rapprochement =
  | { etat: "a_jour" }
  | { etat: "ecart"; ecartCts: number }
  | { etat: "jamais_releve" }
  | { etat: "non_ventile" };

/** Le 512 seul porte ce qui n'est pas rattaché à un compte bancaire. */
export function estNonVentile(compte: CompteAffiche): boolean {
  return compte.compte === "512";
}

export function titreCompte(compte: CompteAffiche): string {
  if (estNonVentile(compte)) return "Opérations sans compte identifié";
  return compte.nom ?? `Compte ${compte.compte}`;
}

/** Comparaison du solde comptable avec le solde de la banque. */
export function rapprochement(compte: CompteAffiche): Rapprochement {
  if (estNonVentile(compte)) return { etat: "non_ventile" };
  if (compte.solde_banque_cts === null || compte.ecart_cts === null) {
    return { etat: "jamais_releve" };
  }
  if (compte.ecart_cts === 0) return { etat: "a_jour" };
  return { etat: "ecart", ecartCts: compte.ecart_cts };
}
