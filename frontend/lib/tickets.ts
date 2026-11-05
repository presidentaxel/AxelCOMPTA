import type { TransactionVue } from "@/lib/types";

/** Lignes de tickets rendues d'un coup quand la liste est dépliée. */
export const TICKETS_PAR_PAGE = 10;

/** Le libellé bancaire suffit : le ticket ne sert pas à classer. */
const CATEGORIES_CLAIRES = new Set([
  "carburant",
  "peage_stationnement",
  "entretien_reparation_vehicule",
  "assurance_vehicule",
  "telecommunications",
  "recettes_plateformes",
  "amendes_infractions",
  "honoraires_comptable_juridique",
  "charges_sociales_impots",
  "loyers_locations",
  "virement_interne",
  "compte_courant_associe",
  "remuneration_dirigeant",
  "frais_bancaires",
  "abonnements_logiciels",
  "fournitures_administratives",
  "subventions",
  "salaires_personnel",
  "usage_personnel",
]);

/** Le ticket est ce qui permet de savoir ce qui a été acheté. */
export function categorieIncertaine(categorie: string): boolean {
  return (
    categorie === "usage_personnel_suspect" ||
    categorie === "non_categorise_a_verifier" ||
    categorie.startsWith("a_verifier")
  );
}

export function categorieDe(depense: TransactionVue): string | null {
  const trouve = depense.libelle.match(/\(([a-z0-9_]+)\)$/);
  return trouve?.[1] ?? depense.proposition;
}

/** Priorité : la pièce sert à lire l'achat et à classer l'écriture.
 * Une dépense déjà claire (carburant, péage, téléphone…) n'est pas demandée. */
export function ticketPrioritaire(depense: TransactionVue): boolean {
  if (depense.montant_cts >= 0 || depense.a_justificatif) return false;
  const categorie = categorieDe(depense);
  if (categorie !== null && categorieIncertaine(categorie)) return true;
  if (depense.statut !== "à trancher") return false;
  return categorie === null || !CATEGORIES_CLAIRES.has(categorie);
}
