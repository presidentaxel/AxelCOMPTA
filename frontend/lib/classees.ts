import { chercheExpert } from "./recherche-expert";
import type { OperationClassee, OperationsClassees } from "./types";

/** Vue « déjà classées » du mode expert (AXE-823) : filtres gardés dans l'URL. */

export const VUE_A_TRAITER = "a_traiter";
export const VUE_RAPPROCHEMENTS = "rapprochements";

export const STATUTS: Record<string, string> = {
  [VUE_A_TRAITER]: "À traiter",
  auto: "Classées automatiquement",
  chauffeur: "Décidées par le chauffeur",
  expert: "Imputées par l'expert",
  toutes: "Toutes les classées",
  [VUE_RAPPROCHEMENTS]: "Rapprochements Rollee",
};

export const ORIGINES: Record<string, string> = {
  regle: "Règle",
  modele: "Modèle",
  humain: "Décision humaine",
  inconnue: "Inconnue",
};

export const TRANCHES: Record<string, string> = {
  basse: "< 0,6",
  moyenne: "0,6 – 0,95",
  haute: "≥ 0,95",
};

export const SENS: Record<string, string> = { entree: "Entrée", sortie: "Sortie" };

export const TRIS: Record<string, string> = {
  recentes: "Plus récentes",
  confiance: "Confiance croissante",
  chauffeur: "Par entreprise",
};

/** Clés lues dans l'URL ; `vue` choisit entre la file et les classées. */
export const CLES = ["vue", "origine", "categorie", "tranche", "sens", "tri", "page", "chauffeur", "q"] as const;
export type Cle = (typeof CLES)[number];
export type EtatClassees = Record<Cle, string>;

const DEFAUTS: EtatClassees = {
  vue: VUE_A_TRAITER,
  origine: "",
  categorie: "",
  tranche: "",
  sens: "",
  tri: "recentes",
  page: "1",
  chauffeur: "",
  q: "",
};

export function lireEtat(recherche: string): EtatClassees {
  const params = new URLSearchParams(recherche);
  const etat = { ...DEFAUTS };
  for (const cle of CLES) {
    const valeur = params.get(cle);
    if (valeur) etat[cle] = valeur;
  }
  if (!(etat.vue in STATUTS)) etat.vue = VUE_A_TRAITER;
  return etat;
}

/** Nouvel état après un changement ; tout filtre changé ramène à la page 1. */
export function changer(etat: EtatClassees, cle: Cle, valeur: string): EtatClassees {
  const suivant = { ...etat, [cle]: valeur };
  if (cle !== "page") suivant.page = "1";
  return suivant;
}

/** Requête de l'URL : seules les valeurs différentes du défaut y figurent. */
export function versRecherche(etat: EtatClassees): string {
  const params = new URLSearchParams();
  for (const cle of CLES) {
    if (etat[cle] && etat[cle] !== DEFAUTS[cle]) params.set(cle, etat[cle]);
  }
  const requete = params.toString();
  return requete ? `?${requete}` : "";
}

/** Paramètres de `GET /expert/classees` (« toutes » : pas de filtre de statut). */
export function versApi(etat: EtatClassees): URLSearchParams {
  const params = new URLSearchParams();
  if (etat.vue !== "toutes" && etat.vue !== VUE_A_TRAITER && etat.vue !== VUE_RAPPROCHEMENTS) {
    params.set("statut", etat.vue);
  }
  for (const cle of ["origine", "categorie", "tranche", "sens", "tri", "page"] as const) {
    if (etat[cle]) params.set(cle, etat[cle]);
  }
  if (etat.chauffeur) params.set("dossier", etat.chauffeur);
  if (etat.q.trim()) params.set("q", etat.q.trim());
  return params;
}

/** Toutes les pages du filtre courant, sans la recherche : elle se fait ensuite
 * en mémoire, à chaque frappe. */
export async function operationsDesPages(
  params: URLSearchParams,
  lire: (params: URLSearchParams) => Promise<OperationsClassees>,
): Promise<OperationClassee[]> {
  const premiere = await lire(params);
  if (premiere.pages <= 1) return premiere.operations;
  const suivantes = await Promise.all(
    Array.from({ length: premiere.pages - 1 }, (_, index) => {
      const suite = new URLSearchParams(params);
      suite.set("page", String(index + 2));
      return lire(suite);
    }),
  );
  return [premiere, ...suivantes].flatMap((page) => page.operations);
}

export async function lireToutesLesPages(
  etat: EtatClassees,
  lire: (params: URLSearchParams) => Promise<OperationsClassees>,
): Promise<OperationClassee[]> {
  return operationsDesPages(versApi({ ...etat, q: "", page: "1" }), lire);
}

export function filtrerOperations(operations: OperationClassee[], saisie: string): OperationClassee[] {
  const texte = saisie.trim();
  if (!texte) return operations;
  return chercheExpert(operations.map(ligneCherchable), texte);
}

/** La page demandée, ou toutes les pages quand une recherche est saisie. */
export async function avecRecherche(
  etat: EtatClassees,
  lire: (params: URLSearchParams) => Promise<OperationsClassees>,
): Promise<OperationsClassees> {
  const premiere = await lire(versApi({ ...etat, q: "", page: "1" }));
  const operations = await lireToutesLesPages(etat, lire);
  const gardees = filtrerOperations(operations, etat.q);
  if (!etat.q.trim()) return { ...premiere, operations };
  return { ...premiere, operations: gardees, total: gardees.length, page: 1, pages: 1 };
}

function ligneCherchable(operation: OperationClassee): OperationClassee {
  const ticket = operation.a_justificatif ? "ticket" : "aucun ticket";
  return { ...operation, detail: [operation.categorie, ticket].filter(Boolean).join(" ") } as OperationClassee & {
    detail: string;
  };
}

export function formatConfiance(confiance: number | null): string {
  return confiance === null ? "—" : confiance.toFixed(2).replace(".", ",");
}

export function phraseCompteurs(c: { auto: number; justes: number; fausses: number }): string {
  return `${c.auto} classées automatiquement, ${c.justes} validées justes, ${c.fausses} marquées fausses`;
}
