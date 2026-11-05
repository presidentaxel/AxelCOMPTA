/** Libellés que le chauffeur voit. Une notion, un nom.
 * Un code inconnu ne s'affiche jamais : le défaut est neutre. */

const DEFAUT = "À classer";

/** Taxonomie du pack VTC et catégories de statut (revue). */
const LIBELLES: Record<string, string> = {
  abonnements_logiciels: "Abonnement",
  a_verifier_location_materiel: "Location à confirmer",
  amendes_infractions: "Amende",
  assurance_personnelle_sante: "Mutuelle",
  assurance_vehicule: "Assurance",
  carburant: "Carburant",
  charges_sociales_impots: "Cotisations et impôts",
  commissions_plateformes: "Commission de plateforme",
  compte_courant_associe: "Apport ou remboursement",
  cotisations_dirigeant: "Mes cotisations sociales",
  dividendes: "Mes dividendes",
  dividendes_associes: "Mes dividendes",
  dotations_amortissements: "Usure du matériel",
  ecarts_reglement_arrondis: "Écart d'arrondi",
  entretien_reparation_vehicule: "Entretien",
  etat_taxes_diverses: "Taxes",
  fournitures_administratives: "Fournitures",
  frais_bancaires: "Frais bancaires",
  honoraires_comptable_juridique: "Honoraires",
  immobilisation_vehicule: "Véhicule",
  impots_dividendes: "Impôts sur mes dividendes",
  interets_emprunts: "Intérêts d'emprunt",
  loa_credit_bail_vehicule: "Location du véhicule",
  loyers_locations: "Loyer",
  non_categorise_a_verifier: DEFAUT,
  operation_capital_hors_perimetre: "Mouvement de capital",
  peage_stationnement: "Péage",
  prelevement_source_paie: "Impôt prélevé sur ma paie",
  recettes_plateformes: "Courses",
  remuneration_dirigeant: "Ma rémunération",
  repas_et_receptions: "Repas",
  salaires_personnel: "Salaire d'un salarié",
  sous_traitance_chauffeurs: "Autre chauffeur",
  subventions: "Aide publique",
  telecommunications: "Téléphone",
  usage_personnel: "Dépense personnelle",
  usage_personnel_suspect: "À confirmer",
  virement_interne: "Virement entre mes comptes",
  visite_medicale_vtc: "Visite médicale",
};

/** Raccourcis de « Autre chose » : les mêmes noms que la table. */
export const RACCOURCIS_CATEGORIE = [
  "dividendes",
  "impots_dividendes",
  "cotisations_dirigeant",
  "prelevement_source_paie",
  "compte_courant_associe",
  "virement_interne",
  "salaires_personnel",
] as const;

export function libelleCategorie(code: string): string {
  const connu = LIBELLES[code];
  if (connu) return connu;
  if (code.startsWith("a_verifier")) return "À confirmer";
  if (/^[a-z0-9_]+$/.test(code)) return DEFAUT;
  return code;
}

export function questionSelonSigne(montantCts: number, sansProposition: boolean): string {
  const sujet =
    montantCts > 0 ? "cette entrée" : montantCts < 0 ? "cette dépense" : "cette opération";
  const question = `À quoi correspond ${sujet} ?`;
  return sansProposition ? `Pas de proposition automatique. ${question}` : question;
}

/** D'où vient la proposition, sans parler du modèle ni d'un pourcentage. */
export function intituleProposition(
  libelle: string,
  origine: "appris" | "regle" | "modele" | "banque" | null,
): string {
  if (origine === "appris") return `Comme une opération déjà classée : ${libelle}`;
  // AXE-826 : la catégorie vient de la banque, pas de nous. On le dit.
  if (origine === "banque") return `D'après votre banque : ${libelle}`;
  return `Proposition : ${libelle}`;
}

/** Une charge de clôture, dite en clair. Le numéro de compte reste interne. */
export const CHARGES_CLOTURE = [
  { compte: "6226", libelle: "Honoraires" },
  { compte: "613", libelle: "Loyer" },
  { compte: "616", libelle: "Assurance" },
  { compte: "6061", libelle: "Carburant" },
  { compte: "6155", libelle: "Entretien" },
  { compte: "626", libelle: "Téléphone" },
  { compte: "618", libelle: "Abonnement" },
  { compte: "606", libelle: "Fournitures" },
  { compte: "658", libelle: "Autre dépense" },
] as const;

export const NOM_NATURE = {
  cca: "Déjà payée, pour plus tard",
  fnp: "Facture pas encore reçue",
} as const;

const REGIMES: Record<string, string> = {
  IS: "l'impôt sur les sociétés",
  IR: "l'impôt sur le revenu",
  option_IR: "l'impôt sur le revenu",
  micro: "le régime micro",
};

/** Une phrase affichée telle quelle quand le serveur l'a déjà écrite. */
export function phrasePourChauffeur(texte: string): string {
  const propre = texte.trim();
  if (propre === "") return propre;
  const debut = propre[0].toLocaleUpperCase("fr-FR") + propre.slice(1);
  return /[.!?…]$/.test(debut) ? debut : `${debut}.`;
}

/** Libellés d'écritures de clôture, gardés comptables en base, dits ici. */
export function phraseEcritureCloture(libelle: string): string {
  if (libelle.startsWith("CCA — ")) {
    return `Déjà payée, pour plus tard — ${libelle.slice("CCA — ".length)}`;
  }
  if (libelle.startsWith("FNP — ")) {
    return `Facture pas encore reçue — ${libelle.slice("FNP — ".length)}`;
  }
  if (libelle.startsWith("À-nouveaux au ")) {
    return `Reprise des comptes au ${libelle.slice("À-nouveaux au ".length)}.`;
  }
  if (libelle === "Liquidation de la TVA de l'exercice") {
    return "Taxe sur les courses (TVA) à reverser pour l'exercice.";
  }
  if (libelle === "Impôt sur les sociétés de l'exercice") {
    return "Impôt sur les bénéfices de la société, pour l'exercice.";
  }
  return phrasePourChauffeur(libelle);
}

/** Changements d'exercice stockés en codes, dits ici. */
export function phraseChangement(texte: string): string {
  const regime = texte.match(/^régime d'imposition : (\S+) → (\S+)$/);
  if (regime) {
    const avant = REGIMES[regime[1] ?? ""] ?? "l'ancien régime";
    const apres = REGIMES[regime[2] ?? ""] ?? "le nouveau régime";
    return `Le régime d'imposition passe de ${avant} à ${apres}.`;
  }
  if (texte === "TVA : sortie de la franchise en base, réel normal") {
    return "Vous sortez de la franchise de TVA : la taxe sera due, au taux réduit.";
  }
  return phrasePourChauffeur(texte);
}
