/** AXE-941 : la fiche d'import d'un chauffeur, côté gestionnaire. Une fiche
 * par chauffeur à reprendre, remplie catégorie par catégorie, avec ses
 * documents. Compilé seul pour les tests. */

export type StatutImport = "a_importer" | "en_traitement" | "traitee";

export type ChoixImport = { cle: string; libelle: string };

export type ChampImport = {
  cle: string;
  libelle: string;
  type:
    | "texte"
    | "long"
    | "date"
    | "siren"
    | "email"
    | "telephone"
    | "choix"
    | "multi"
    | "montant"
    | "annee"
    | "jour_mois"
    | "siret"
    | "associes"
    | "rollee";
  obligatoire: boolean;
  choix: ChoixImport[];
  aide: string;
  valeur: string;
};

export type SectionImport = {
  cle: string;
  libelle: string;
  description: string;
  complet: boolean;
  manquants: string[];
  champs: ChampImport[];
};

export type ExerciceImport = { annee: number; debut: string; fin: string; etat: "clos" | "en_cours" };

/** AXE-947 : ce qui a été tiré d'un document. */
export type StatutDocument = "traite" | "a_traiter" | "illisible";

export type DocumentImport = {
  id: string;
  categorie: string;
  libelle: string;
  exercice: number | null;
  emplacement: string;
  nom_fichier: string;
  taille: number;
  depose_par: string;
  depose_le: string;
  statut_traitement: StatutDocument;
  resume: string;
};

/** AXE-947 : un document attendu, son explication et ce qui y est déposé. */
export type EmplacementImport = {
  cle: string;
  section: string;
  libelle: string;
  explication: string;
  attendu: boolean;
  documents: DocumentImport[];
};

export type FicheImportResume = {
  id: string;
  nom: string;
  prenom: string;
  denomination: string | null;
  siren: string | null;
  statut: StatutImport;
  sections_completes: number;
  sections: number;
  documents_a_lire: number;
  dossier_id: string | null;
  maj_par: string;
  maj_le: string;
};

export type FicheImport = FicheImportResume & {
  sections_detail: SectionImport[];
  exercices: ExerciceImport[];
  emplacements: EmplacementImport[];
  registre_lu_le: string | null;
  registre_sources: string[];
  depuis_registre: string[];
  manque_pour_creer: string[];
  dossier_prevu: string | null;
  dossier_cree: boolean;
};

export const STATUTS_IMPORT: { cle: StatutImport; libelle: string }[] = [
  { cle: "a_importer", libelle: "À importer" },
  { cle: "en_traitement", libelle: "En traitement" },
  { cle: "traitee", libelle: "Traitée" },
];

export function libelleStatut(statut: StatutImport): string {
  return STATUTS_IMPORT.find((s) => s.cle === statut)?.libelle ?? statut;
}

/** Badge du design system (DESIGN.md › Badges) pour un statut. */
export function badgeStatut(statut: StatutImport): "missing" | "pending" | "validated" {
  if (statut === "traitee") return "validated";
  return statut === "en_traitement" ? "pending" : "missing";
}

/** « Karim Dupont », ou l'entreprise si le chauffeur n'a pas de nom. */
export function nomChauffeur(fiche: Pick<FicheImportResume, "nom" | "prenom" | "denomination">): string {
  const nom = [fiche.prenom, fiche.nom].filter(Boolean).join(" ");
  return nom || fiche.denomination || "Chauffeur sans nom";
}

export function etatSection(section: Pick<SectionImport, "complet" | "manquants">): string {
  if (section.complet) return "Complet";
  const n = section.manquants.length;
  return `${n} à compléter`;
}

export function taille(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1).replace(".", ",")} Mo`;
}

/** Les champs qui ont changé, prêts à envoyer ; `{}` si rien n'a bougé. */
export function champsModifies(section: SectionImport, saisie: Record<string, string>): Record<string, string> {
  const modifies: Record<string, string> = {};
  for (const champ of section.champs) {
    const valeur = saisie[champ.cle];
    if (valeur !== undefined && valeur.trim() !== champ.valeur) modifies[champ.cle] = valeur.trim();
  }
  return modifies;
}

/** Un champ « multi » est rangé « uber,bolt ». */
export function basculerChoix(valeur: string, cle: string): string {
  const choisis = valeur ? valeur.split(",") : [];
  const suivants = choisis.includes(cle) ? choisis.filter((c) => c !== cle) : [...choisis, cle];
  return suivants.join(",");
}

// --- AXE-946 ---------------------------------------------------------------

export type Associe = { prenom: string; nom: string; fonction: string; pourcentage: string };
export type CompteRolleeRetenu = { rollee_user_id: string; nom: string; plateformes: string[] };

/** Une liste rangée en JSON ; une ancienne saisie libre se lit vide. */
export function lireListe<T>(valeur: string): T[] {
  try {
    const donnees = JSON.parse(valeur || "[]") as unknown;
    return Array.isArray(donnees) ? (donnees as T[]) : [];
  } catch {
    return [];
  }
}

export function totalParts(associes: Associe[]): number {
  const total = associes.reduce((somme, a) => somme + (Number(a.pourcentage.replace(",", ".")) || 0), 0);
  return Math.round(total * 100) / 100;
}

/** Le SIREN ou le SIRET saisi, sans espaces, s'il a la bonne longueur. */
export function identifiantComplet(texte: string): string | null {
  const chiffres = texte.replace(/[\s.]/g, "");
  return /^\d{9}$|^\d{14}$/.test(chiffres) ? chiffres : null;
}

const MOTIFS_CATEGORIE: [RegExp, string][] = [
  [/fec|ecritures|écritures/i, "fec"],
  [/liasse|2033|2031|2065|2035|bilan/i, "liasse"],
  [/balance/i, "balance"],
  [/grand[ ._-]?livre|\bgl\b/i, "grand_livre"],
  [/kbis|k-bis|extrait/i, "kbis"],
  [/statut/i, "statuts"],
  [/\brib\b|iban/i, "rib"],
  [/lettre|mission|confr[eè]re/i, "lettre_comptable"],
  [/relev[eé]|releve/i, "releve_bancaire"],
];

/** Le type d'un document deviné de son nom ; `repli` si rien ne parle. */
export function devinerCategorie(nom: string, permises: string[], repli: string): string {
  const trouve = MOTIFS_CATEGORIE.find(([motif, cle]) => permises.includes(cle) && motif.test(nom));
  return trouve ? trouve[1] : repli;
}

/** L'exercice lu dans le nom (« liasse-2024.pdf »), s'il est proposé. */
export function devinerExercice(nom: string, annees: number[]): number | null {
  const lues = nom.match(/20\d\d/g) ?? [];
  const annee = lues.map(Number).find((a) => annees.includes(a));
  return annee ?? null;
}

export function progression(fiche: Pick<FicheImportResume, "sections_completes" | "sections">): number {
  return fiche.sections === 0 ? 0 : Math.round((fiche.sections_completes / fiche.sections) * 100);
}

/** La valeur d'un champ, où qu'il soit dans la fiche ; « » s'il est vide. */
export function valeurChamp(fiche: Pick<FicheImport, "sections_detail">, cle: string): string {
  for (const section of fiche.sections_detail) {
    const champ = section.champs.find((c) => c.cle === cle);
    if (champ) return champ.valeur;
  }
  return "";
}

// --- AXE-947 ---------------------------------------------------------------

export type ContactDigifactory = {
  contact_nr: string;
  nom: string;
  siren: string | null;
  raison: string;
  a_un_dossier: boolean;
};
export type DigifactoryFiche = { lu: boolean; contacts: ContactDigifactory[] };

export function libelleTraitement(statut: StatutDocument): string {
  if (statut === "traite") return "Lu automatiquement";
  return statut === "illisible" ? "Illisible" : "À lire";
}

/** « reprise:liasse:2025 » → 2025 ; `null` hors exercice. */
export function anneeEmplacement(cle: string): number | null {
  const annee = cle.split(":")[2];
  return annee ? Number(annee) : null;
}

/** Les emplacements d'une catégorie, rangés par exercice (le plus récent
 * d'abord) ; ceux sans exercice à la fin, sous `null`. */
export function parExercice(emplacements: EmplacementImport[]): [number | null, EmplacementImport[]][] {
  const groupes = new Map<number | null, EmplacementImport[]>();
  for (const e of emplacements) {
    const annee = anneeEmplacement(e.cle);
    groupes.set(annee, [...(groupes.get(annee) ?? []), e]);
  }
  return [...groupes.entries()].sort(([a], [b]) => (b ?? -1) - (a ?? -1));
}
