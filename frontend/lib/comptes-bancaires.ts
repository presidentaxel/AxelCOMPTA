// AXE-832 : présentation des comptes bancaires du chauffeur. Pur, sans
// React ni réseau, pour être testé avec `npm run test:unit`.

export type CompteAffiche = {
  compte: string;
  nom: string | null;
  solde_comptable_cts: number;
  solde_banque_cts: number | null;
  ecart_cts: number | null;
  retenu?: boolean | null;
  propose_par_fiche?: boolean | null;
};

export type ChoixCompte = "retenu" | "ecarte" | "a_decider";

/** AXE-729. Un compte sans réponse de l'API (ancienne version) est retenu. */
export function choixCompte(compte: CompteAffiche): ChoixCompte {
  if (compte.retenu === false) return "ecarte";
  if (compte.retenu === null) return "a_decider";
  return "retenu";
}

/** AXE-986 : ce que la fiche d'import dit du compte, à confirmer ou en
 * désaccord avec le choix enregistré. `null` : rien à signaler. */
export function phraseFiche(compte: CompteAffiche): string | null {
  const propose = compte.propose_par_fiche;
  if (propose === undefined || propose === null) return null;
  const usage = propose ? "compte de l'activité" : "compte personnel";
  const choix = choixCompte(compte);
  if (choix === "a_decider") return `La fiche d'import propose : ${usage}.`;
  if ((choix === "retenu") !== propose) return `La fiche d'import dit autre chose : ${usage}.`;
  return null;
}

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
  // Pas comptabilisé : rien à rapprocher.
  if (choixCompte(compte) !== "retenu") return { etat: "jamais_releve" };
  if (compte.solde_banque_cts === null || compte.ecart_cts === null) {
    return { etat: "jamais_releve" };
  }
  if (compte.ecart_cts === 0) return { etat: "a_jour" };
  return { etat: "ecart", ecartCts: compte.ecart_cts };
}
