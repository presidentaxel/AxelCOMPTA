/** AXE-802 : registre des immobilisations du chauffeur (véhicule surtout). */

export type ImmobilisationVue = {
  id: string;
  designation: string;
  compte: string;
  mise_en_service: string;
  base_cts: number;
  duree_mois: number;
  dotation_exercice_cts: number;
  valeur_nette_cts: number;
  cede_le: string | null;
  prix_cession_cts: number | null;
  plus_ou_moins_value_cts: number | null;
};

export type BienADeclarerVue = {
  ecriture_id: string;
  date: string;
  libelle: string;
  compte: string;
  base_cts: number;
  duree_proposee_mois: number;
};

export type RegistreImmobilisationsVue = {
  immobilisations: ImmobilisationVue[];
  a_declarer: BienADeclarerVue[];
};

/** « 5 ans », « 18 mois » : la durée dite comme le chauffeur la pense. */
export function dureeEnClair(mois: number): string {
  if (mois % 12 === 0) {
    const ans = mois / 12;
    return ans === 1 ? "1 an" : `${ans} ans`;
  }
  return `${mois} mois`;
}

/** Ce que la vente a rapporté ou coûté, comparé à la valeur restante. */
export function phraseCession(valeurCts: number | null): string | null {
  if (valeurCts === null) return null;
  if (valeurCts === 0) return "Vendu à sa valeur restante.";
  return valeurCts > 0 ? "Plus-value à la vente" : "Moins-value à la vente";
}

/** Une durée saisie en années, bornée à ce que le serveur accepte. */
export function lireDureeAnnees(saisie: string): number | null {
  const ans = Number(saisie.replace(",", "."));
  if (!Number.isFinite(ans) || ans < 1 || ans > 50) return null;
  return Math.round(ans * 12);
}
