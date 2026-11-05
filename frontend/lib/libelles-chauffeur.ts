/** Libellés vus par le chauffeur. Un code inconnu ne s'affiche jamais :
 * le repli est une phrase, pas le code brut. */

const LIBELLES: Record<string, string> = {
  usage_personnel_suspect: "À confirmer",
  usage_personnel: "Dépense personnelle",
  non_categorise_a_verifier: "À préciser",
  a_verifier_location_materiel: "Location de matériel",
  carburant: "Carburant",
  peage_stationnement: "Péage ou stationnement",
  repas_et_receptions: "Repas",
  assurance_vehicule: "Assurance du véhicule",
  assurance_personnelle_sante: "Assurance personnelle",
  telecommunications: "Téléphone",
  entretien_reparation_vehicule: "Entretien du véhicule",
  charges_sociales_impots: "Charges sociales",
  honoraires_comptable_juridique: "Honoraires",
  recettes_plateformes: "Courses",
  commissions_plateformes: "Commission de plateforme",
  remuneration_dirigeant: "Ma rémunération",
  compte_courant_associe: "Apport ou remboursement",
  virement_interne: "Virement entre mes comptes",
  salaires_personnel: "Salaire d'un salarié",
  frais_bancaires: "Frais bancaires",
  abonnements_logiciels: "Abonnement",
  fournitures_administratives: "Fournitures",
  amendes_infractions: "Amende",
  subventions: "Aide publique",
  loyers_locations: "Loyer",
  cotisations_dirigeant: "Mes cotisations sociales",
  dividendes: "Mes dividendes",
  dividendes_associes: "Mes dividendes",
  impots_dividendes: "Impôts sur mes dividendes",
  prelevement_source_paie: "Impôt prélevé sur ma paie",
  immobilisation_vehicule: "Achat du véhicule",
  loa_credit_bail_vehicule: "Location du véhicule",
  sous_traitance_chauffeurs: "Autre chauffeur",
  dotations_amortissements: "Usure du véhicule",
  interets_emprunts: "Intérêts d'emprunt",
  etat_taxes_diverses: "Taxes",
  ecarts_reglement_arrondis: "Écart d'arrondi",
  operation_capital_hors_perimetre: "Opération sur le capital",
  visite_medicale_vtc: "Visite médicale",
};

const DEFAUT = "À préciser";

export function libelleCategorie(code: string): string {
  if (code.startsWith("a_verifier")) {
    return LIBELLES[code] ?? DEFAUT;
  }
  return LIBELLES[code] ?? DEFAUT;
}

export function questionPour(montantCts: number, avecProposition: boolean): string {
  const sujet = montantCts < 0 ? "cette dépense" : "cette entrée";
  if (avecProposition) {
    return montantCts < 0 ? "C'est bien cette dépense ?" : "C'est bien cette entrée ?";
  }
  return `À quoi correspond ${sujet} ?`;
}

/** Natures de charge proposées au chauffeur. Le numéro de compte reste ici. */
export const CHARGES_PROVISION: Array<{ compte: string; libelle: string }> = [
  { compte: "606", libelle: "Carburant ou achat" },
  { compte: "615", libelle: "Entretien" },
  { compte: "616", libelle: "Assurance" },
  { compte: "613", libelle: "Loyer" },
  { compte: "626", libelle: "Téléphone" },
  { compte: "622", libelle: "Honoraires" },
  { compte: "625", libelle: "Repas ou déplacement" },
  { compte: "628", libelle: "Autre charge" },
];

export function libelleCharge(compte: string): string {
  return CHARGES_PROVISION.find((charge) => charge.compte === compte)?.libelle ?? "Charge";
}

export const NATURE_PROVISION = {
  fnp: "Facture pas encore reçue",
  cca: "Déjà payée, pour plus tard",
} as const;
