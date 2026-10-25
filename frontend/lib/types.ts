// Miroir des modèles Pydantic de axelcompta/demo_api.py — garder les deux
// synchronisés à la main (pas de génération OpenAPI pour la démo, doc 17 §8).

export type RegimeAVenir = {
  exercice: number;
  regime: string;
  motif: string;
};

export type DossierResume = {
  dossier_id: string;
  nom: string;
  tva_recettes_regime: string;
  plateformes: string[];
  exercice_debut: string | null;
  exercice_fin: string | null;
  ca_ht_cts: number;
  charges_cts: number;
  resultat_cts: number;
  tresorerie_cts: number;
  tva_a_payer_cts: number;
  nb_transactions: number;
  nb_a_trancher: number;
  statut_invitation: "invité" | "actif" | null; // null = "non_invité" (doc 19 §3.2)
  mode_acces_bancaire: "gestionnaire" | "chauffeur_direct"; // doc 19 §4
  peut_connecter_sa_banque: boolean; // faux tant que le faux Digifactory de la démo est branché
  cloture_faite: boolean; // preuve de clôture : la validation de liasse se fait au téléchargement
  greffe_inpi_signe: boolean; // doc 20 : dossier de dépôt signé (démo, jamais qualifié RGS)
  guide_greffe: GuideGreffe;
  // Lus dans la matrice des statuts côté API : 2065 à l'IS, 2031 à l'IR.
  declaration_resultat: "2065" | "2031";
  depot_greffe: boolean;
  // Approche du terme de l'option IR et changements de régime à venir.
  alerte_regime: string | null;
  regimes_a_venir: RegimeAVenir[];
  // Franchise en base : approche ou dépassement des seuils de l'année.
  alerte_tva: string | null;
  // Président assimilé salarié : sa paie se saisit depuis son bulletin.
  paie_par_bulletin: boolean;
  forme_juridique: string;
  regime_libelle: string;
};

export type LignePortail = {
  question: string;
  reponse: string;
  detail: string;
};

export type PieceGreffe = {
  nom: string;
  detail: string;
  document: string | null;
};

export type GuideGreffe = {
  depose: boolean;
  lien: string;
  lignes: LignePortail[];
  pieces: PieceGreffe[];
};

// Vue gestionnaire (doc 19 §2.1/§2.4) : agrégats et onboarding seulement.
// Miroir de `DossierAgregat` (demo_api.py), volontairement distinct de
// `DossierResume` : rien de dérivé du détail d'un dossier n'y figure.
export type DossierAgregat = {
  dossier_id: string;
  nom: string;
  tva_recettes_regime: string;
  plateformes: string[];
  exercice_debut: string | null;
  exercice_fin: string | null;
  ca_ht_cts: number;
  charges_cts: number;
  resultat_cts: number;
  statut_invitation: "invité" | "actif" | null;
  mode_acces_bancaire: "gestionnaire" | "chauffeur_direct";
  forme_juridique: string;
  regime_imposition: string;
  regime_tva: string;
  annee_courante: number;
  etape_courante: string;
  annee_precedente: number;
  etape_precedente: string;
  alerte_regime: string | null;
  alerte_tva: string | null;
};

export type AlerteAnomalie = {
  id: string;
  code: string;
  libelle_ui: string;
  detail: string;
  etat: "ouverte" | "en_instruction" | "justifiee" | "usage_personnel" | "faux_positif";
  libelle_mouvement: string;
  montant_centimes: number;
  date: string;
};

export type SujetExpert = {
  id: string;
  dossier_id: string;
  dossier_nom: string;
  cote: "chauffeur" | "gestionnaire";
  nature: "a_trancher" | "ticket" | "anomalie";
  libelle: string;
  detail: string;
  montant_cts: number | null;
  ecriture_id: string | null;
  imputable: boolean;
};

export type FileExpert = {
  sujets: SujetExpert[];
  comptes: { compte: string; libelle: string }[];
};

// doc 17 §9 Semaine 4 + AXE-417/418 : exports de clôture (PDF + CSV),
// servis en téléchargement direct par demo_api.py.
export type DocumentCloture =
  | "liasse-fiscale.pdf"
  | "liasse.pdf"
  | "cerfa-2065.pdf"
  | "cerfa-2031.pdf"
  | "fec.txt"
  | "grand-livre.pdf"
  | "grand-livre.csv"
  | "balance.pdf"
  | "balance.csv";

// doc 20 §4 : réponse de la signature greffe/INPI — déplacé ici le
// 2026-09-11 (doc 19) car appelé depuis lib/api.ts (type) et
// lib/auth-chauffeur.ts (l'appel authentifié réel, côté indiv).
/** Cloche de l'espace chauffeur : posée par les tâches planifiées. */
export type NotificationVue = {
  id: string;
  message: string;
  cree_le: string;
  lue: boolean;
};

export type SignatureGreffeVue = {
  dossier_id: string;
  signe: boolean;
  signe_le: string;
  qualifie: boolean; // toujours false en démo
};

export type StatutTransaction = "validé" | "à trancher";

export type TransactionVue = {
  ecriture_id: string;
  date: string;
  libelle: string;
  montant_cts: number;
  compte: string;
  statut: StatutTransaction;
  a_justificatif: boolean; // doc 17 §9 Semaine 3 : photo jointe (contenu non lu)
  // Proposition pour une opération à trancher, calculée à chaque lecture :
  // une opération semblable déjà classée par le chauffeur (« appris »), sinon
  // les règles (« regle ») ou le modèle (« modele »). null : pas de proposition.
  proposition: string | null;
  origine_proposition: "appris" | "regle" | "modele" | null;
  confiance_proposition: number | null;
};

/** Clôture de l'exercice, préparée par l'API et validée par le chauffeur
 * seul (doc 06 §5). `attestation` se renvoie mot pour mot pour valider. */
export type ProvisionClotureVue = {
  nature: "cca" | "fnp";
  compte_charge: string;
  centimes: number;
  libelle: string;
};

export type ClotureExerciceVue = {
  possible: boolean;
  raison: string | null;
  exercice_debut: string;
  exercice_fin: string;
  nouvel_exercice_debut: string | null;
  ecritures: string[];
  changements: string[];
  attestation: string | null;
};

/** Affectation du résultat : scénarios chiffrés par l'API, choix du
 * chauffeur seul (Louis, 2026-09-26). Montants en centimes. */
export type ScenarioAffectation = {
  cle: string;
  libelle: string;
  dividendes_cts: number;
  impot_revenu_cts: number;
  prelevements_sociaux_cts: number;
  part_soumise_cotisations_cts: number;
  net_percu_cts: number;
  laisse_en_societe_cts: number;
  tresorerie_apres_cts: number;
};

export type AffectationVue = {
  applicable: boolean;
  raison: string | null;
  annee_exercice: number | null;
  resultat_cts: number;
  reserve_legale_cts: number;
  distribuable_cts: number;
  disponible_cts: number;
  scenarios: ScenarioAffectation[];
  avertissements: string[];
};

/** Versement des dividendes décidés : retenues à la source et 2777. */
export type DividendesVue = {
  applicable: boolean;
  raison: string | null;
  annee_exercice: number | null;
  brut_cts: number;
  declare: boolean;
  verse_le: string | null;
  dispense_prelevement: boolean;
  prelevement_forfaitaire_cts: number;
  csg_cts: number;
  crds_cts: number;
  solidarite_cts: number;
  total_retenu_cts: number;
  net_a_virer_cts: number;
  echeance_2777: string | null;
};

export type BulletinVue = {
  mois: string;
  brut_cts: number;
  net_a_payer_cts: number;
};
