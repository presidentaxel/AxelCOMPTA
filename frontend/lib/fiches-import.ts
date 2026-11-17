/** AXE-941 : la fiche d'import d'un chauffeur, côté gestionnaire. Une fiche
 * par chauffeur à reprendre, remplie catégorie par catégorie, avec ses
 * documents. Compilé seul pour les tests. */

export type StatutImport = "a_importer" | "en_traitement" | "traitee" | "ignore";

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

export type ExerciceImport = {
  annee: number;
  debut: string;
  fin: string;
  etat: "clos" | "en_cours";
  /** AXE-950 : à déclarer par nous, source du report à nouveau, ou antérieur. */
  role: "en_cours" | "a_declarer" | "source" | "anterieur";
  echeance: string | null;
  en_retard: boolean;
};

/** AXE-947 : ce qui a été tiré d'un document. */
export type StatutDocument = "traite" | "a_traiter" | "illisible";

export type DocumentImport = {
  id: string;
  /** AXE-970 : l'archive zip d'où il a été sorti. */
  origine_id?: string | null;
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
  { cle: "ignore", libelle: "Ignoré" },
];

export function libelleStatut(statut: StatutImport): string {
  return STATUTS_IMPORT.find((s) => s.cle === statut)?.libelle ?? statut;
}

/** Badge du design system (DESIGN.md › Badges) pour un statut. */
export function badgeStatut(statut: StatutImport): "missing" | "pending" | "validated" | "closed" {
  if (statut === "traitee") return "validated";
  if (statut === "ignore") return "closed";
  return statut === "en_traitement" ? "pending" : "missing";
}

/** Ignoré ne compte ni dans Toutes, ni dans Entreprises. */
export function fichesActives<T extends { statut: StatutImport }>(fiches: T[]): T[] {
  return fiches.filter((fiche) => fiche.statut !== "ignore");
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

export type UsageCompte = "pro" | "perso";

/** Un compte tel que la fiche le garde : l'IBAN complet n'est pas enregistré,
 * seulement ses 4 derniers caractères, pour le reconnaître sans le recopier. */
export type CompteBancaireFiche = {
  id: string;
  nom: string;
  banque: string;
  fin: string;
  usage: UsageCompte | "";
};

/** Un compte lu chez Digifactory, avant le choix pro / perso. */
export type CompteDigifactoryFiche = {
  id: string;
  nom: string;
  banque: string;
  iban: string;
  professionnel: boolean | null;
};

export type ComptesDigifactory = { lu: boolean; comptes: CompteDigifactoryFiche[] };

const USAGES: ReadonlySet<string> = new Set(["pro", "perso"]);

function finIban(iban: string): string {
  return iban.replace(/\s/g, "").slice(-4);
}

/** « FR76 3000 … 0189 », ou « •••• 0189 » si seul le rappel est connu. */
export function libelleIban(iban: string, fin: string): string {
  const compact = iban.replace(/\s/g, "").toUpperCase();
  if (compact) return compact.replace(/(.{4})/g, "$1 ").trim();
  return fin ? `•••• ${fin}` : "";
}

function usageDe(valeur: unknown): UsageCompte | "" {
  return typeof valeur === "string" && USAGES.has(valeur) ? (valeur as UsageCompte) : "";
}

function compteJson(ligne: unknown): CompteBancaireFiche | null {
  if (typeof ligne !== "object" || ligne === null || !("id" in ligne)) return null;
  const brut = ligne as Record<string, unknown>;
  const id = typeof brut.id === "string" ? brut.id : "";
  if (!id) return null;
  return {
    id,
    nom: typeof brut.nom === "string" ? brut.nom : "",
    banque: typeof brut.banque === "string" ? brut.banque : "",
    fin: typeof brut.fin === "string" ? brut.fin : "",
    usage: usageDe(brut.usage),
  };
}

/** « Compte courant (retenu) » : la forme écrite par la synchro avant le choix. */
function compteLegacy(ligne: string): CompteBancaireFiche {
  const lu = /^(.*?)\s*\((retenu|écarté|à choisir)\)\s*$/.exec(ligne);
  if (!lu) return { id: ligne, nom: ligne, banque: "", fin: "", usage: "" };
  const nom = lu[1].trim();
  const usage = lu[2] === "retenu" ? "pro" : lu[2] === "écarté" ? "perso" : "";
  return { id: nom || ligne, nom, banque: "", fin: "", usage };
}

/** Les choix déjà sur la fiche : JSON, ou les lignes « Nom (retenu) » d'avant. */
export function lireComptesChoisis(valeur: string): CompteBancaireFiche[] {
  const json = lireListe<unknown>(valeur).map(compteJson).filter((c) => c !== null);
  if (json.length > 0) return json;
  return valeur
    .split("\n")
    .map((ligne) => ligne.trim())
    .filter(Boolean)
    .map(compteLegacy);
}

export function ecrireComptesChoisis(comptes: CompteBancaireFiche[]): string {
  if (comptes.length === 0) return "";
  return JSON.stringify(
    comptes.map(({ id, nom, banque, fin, usage }) => ({ id, nom, banque, fin, usage })),
  );
}

/** La liste à montrer : les comptes Digifactory, avec le choix déjà fait
 * (par identifiant, sinon par nom pour les anciennes lignes). Sans réponse
 * Digifactory, ce qui est déjà sur la fiche. */
export function fusionnerComptes(
  live: CompteDigifactoryFiche[] | null,
  sauves: CompteBancaireFiche[],
): (CompteBancaireFiche & { iban: string; professionnel: boolean | null })[] {
  if (live === null || live.length === 0) {
    return sauves.map((compte) => ({ ...compte, iban: "", professionnel: null }));
  }
  const parId = new Map(sauves.map((compte) => [compte.id, compte.usage]));
  const parNom = new Map(
    sauves.filter((compte) => compte.nom).map((compte) => [compte.nom, compte.usage]),
  );
  return live.map((compte) => ({
    id: compte.id,
    nom: compte.nom,
    banque: compte.banque,
    fin: finIban(compte.iban),
    usage: parId.has(compte.id) ? (parId.get(compte.id) ?? "") : (parNom.get(compte.nom) ?? ""),
    iban: compte.iban,
    professionnel: compte.professionnel,
  }));
}

export type ContactDigifactory = {
  contact_nr: string;
  nom: string;
  siren: string | null;
  raison: string;
  a_un_dossier: boolean;
};
export type DigifactoryFiche = { lu: boolean; contacts: ContactDigifactory[] };
export type HistoriqueDigifactory = { lu: boolean; debut: string | null };

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

/** AXE-950 : ce qu'est l'exercice pour la reprise, en une phrase. */
export function phraseExercice(e: ExerciceImport): string {
  const echeance = e.echeance ? new Date(e.echeance).toLocaleDateString("fr-FR") : "";
  if (e.role === "en_cours") return "En cours : la banque et Rollee le rempliront.";
  if (e.role === "a_declarer") {
    return e.en_retard
      ? `Jamais déposé (date limite dépassée le ${echeance}) : à déclarer par nous, en retard.`
      : `À déclarer par nous : liasse avant le ${echeance}.`;
  }
  if (e.role === "source") return "Déjà déposé : sa liasse et son FEC donnent le report à nouveau.";
  return "Déjà déposé : documents utiles s'ils sont disponibles.";
}

/** Le bouton « Pas déposée (en retard) » n'a de sens qu'une fois la date limite passée. */
export function retardPossible(e: ExerciceImport): boolean {
  return e.en_retard || e.role === "source" || e.role === "anterieur";
}

export function basculerRetard(enRetard: string, annee: number): string {
  return basculerChoix(enRetard, String(annee)).split(",").filter(Boolean).sort().join(",");
}

// --- AXE-970 : tout l'historique, exercice par exercice ----------------------

export const ANNEE_MIN_REPRISE = 2000;

/** Où ranger une pièce d'un exercice : les catégories proposées au reclassement. */
export const CATEGORIES_EXERCICE: { cle: string; libelle: string }[] = [
  { cle: "liasse", libelle: "Liasse fiscale" },
  { cle: "fec", libelle: "FEC" },
  { cle: "balance", libelle: "Balance" },
  { cle: "grand_livre", libelle: "Grand livre" },
  { cle: "comptes_annuels", libelle: "Bilan et compte de résultat" },
  { cle: "declaration_tva", libelle: "Déclarations de TVA" },
  { cle: "declaration_is", libelle: "Déclarations d'IS" },
  { cle: "accuse_reception", libelle: "Accusés de réception" },
  { cle: "paiement_impot", libelle: "Paiements d'impôts" },
  { cle: "piece", libelle: "Pièces justificatives" },
  { cle: "archive", libelle: "Archive" },
  { cle: "autre", libelle: "Autre document" },
];

/** L'année saisie pour « Ajouter un exercice », ou le message d'erreur. */
export function lireAnnee(texte: string, aujourdhui: Date): number | string {
  const annee = Number(texte.trim());
  const max = aujourdhui.getFullYear();
  if (!/^\d{4}$/.test(texte.trim()) || annee < ANNEE_MIN_REPRISE || annee > max) {
    return `Une année de clôture, de ${ANNEE_MIN_REPRISE} à ${max}.`;
  }
  return annee;
}

/** La liste « 2015,2019 » avec une année de plus, triée et sans doublon. */
export function ajouterAnnee(liste: string, annee: number): string {
  const annees = new Set(liste.split(",").filter(Boolean).map(Number));
  annees.add(annee);
  return [...annees].sort((a, b) => a - b).join(",");
}

/** Une carte qui reçoit une archive peut avoir des dizaines de pièces : on en
 * montre `max`, le reste sur demande. */
export function documentsVisibles<T>(documents: T[], tout: boolean, max = 5): { visibles: T[]; caches: number } {
  if (tout || documents.length <= max) return { visibles: documents, caches: 0 };
  return { visibles: documents.slice(0, max), caches: documents.length - max };
}
