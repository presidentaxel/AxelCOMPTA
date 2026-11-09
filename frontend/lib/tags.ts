import type { DossierAgregat } from "./types";

/** Valeurs du filtre « Tag » d'Entreprises (paramètre `tag` de l'URL). */
export const TOUS_LES_TAGS = "tous";
export const SANS_TAG = "sans_tag";

const LIBELLES: Record<string, string> = {
  chauffeur: "Chauffeur",
  societe_du_gestionnaire: "Société du gestionnaire",
  hors_perimetre: "Hors périmètre",
  test: "Test",
};

/** Nom lisible d'un tag : les tags proposés ont un libellé, les autres
 * s'affichent sans les « _ ». */
export function libelleTag(nom: string): string {
  return LIBELLES[nom] ?? nom.replaceAll("_", " ");
}

/** Le dossier passe le filtre de tag choisi. */
export function gardeTag(dossier: Pick<DossierAgregat, "tags">, filtre: string): boolean {
  if (filtre === TOUS_LES_TAGS) return true;
  if (filtre === SANS_TAG) return dossier.tags.length === 0;
  return dossier.tags.includes(filtre);
}

export type TotauxPortefeuille = { nombre: number; sansCompte: number; resultat: number };

/** Compteurs d'Entreprises : un dossier exclu des compteurs par un tag
 * (société du gestionnaire, hors périmètre…) n'y entre pas. */
export function totauxPortefeuille(
  dossiers: Pick<DossierAgregat, "exclu_compteurs" | "statut_invitation" | "resultat_cts">[],
): TotauxPortefeuille {
  const comptes = dossiers.filter((dossier) => !dossier.exclu_compteurs);
  return {
    nombre: comptes.length,
    sansCompte: comptes.filter((dossier) => dossier.statut_invitation === null).length,
    resultat: comptes.reduce((somme, dossier) => somme + dossier.resultat_cts, 0),
  };
}

/** Bascule d'un tag dans la liste des tags exclus d'un traitement. */
export function basculerExclusion(exclus: string[], tag: string): string[] {
  return exclus.includes(tag) ? exclus.filter((nom) => nom !== tag) : [...exclus, tag].sort();
}

/** Tags présents dans une file (mode expert), triés, pour proposer le filtre. */
export function tagsPresents(tagsParDossier: Record<string, string[]>): string[] {
  return [...new Set(Object.values(tagsParDossier).flat())].sort();
}

/** Lecture du paramètre `tag` d'une URL ; absent : tous. */
export function lireFiltreTag(recherche: string): string {
  return new URLSearchParams(recherche).get("tag") || TOUS_LES_TAGS;
}

/** URL avec le filtre de tag écrit (ou retiré pour « tous »). */
export function ecrireFiltreTag(chemin: string, recherche: string, tag: string): string {
  const params = new URLSearchParams(recherche);
  if (tag === TOUS_LES_TAGS) params.delete("tag");
  else params.set("tag", tag);
  const requete = params.toString();
  return requete ? `${chemin}?${requete}` : chemin;
}
