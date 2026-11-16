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
    | "jour_mois";
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

export type PieceImport = { categorie: string; libelle: string; attendue: boolean; recue: boolean };

export type ExerciceImport = {
  annee: number;
  debut: string;
  fin: string;
  etat: "clos" | "en_cours";
  pieces: PieceImport[];
};

export type DocumentImport = {
  id: string;
  categorie: string;
  libelle: string;
  exercice: number | null;
  nom_fichier: string;
  taille: number;
  depose_par: string;
  depose_le: string;
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
  dossier_id: string | null;
  maj_par: string;
  maj_le: string;
};

export type FicheImport = FicheImportResume & {
  sections_detail: SectionImport[];
  exercices: ExerciceImport[];
  documents: DocumentImport[];
  categories_documents: ChoixImport[];
  registre_lu_le: string | null;
  registre_sources: string[];
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
