import { changer, CLES, lireEtat, VUE_A_TRAITER, type EtatClassees } from "./classees";

/** Les filtres sont tout sauf la vue, le tri et la page : un tri choisi ne
 * « filtre » rien, il ne doit pas proposer de réinitialisation. */
const FILTRES = CLES.filter((cle) => cle !== "vue" && cle !== "tri" && cle !== "page");

export function filtresActifs(etat: EtatClassees): boolean {
  return FILTRES.some((cle) => etat[cle] !== "");
}

/** Même vue et même tri, sans aucun filtre, de retour à la première page. */
export function sansFiltres(etat: EtatClassees): EtatClassees {
  const suivant = { ...etat };
  for (const cle of FILTRES) suivant[cle] = "";
  suivant.page = lireEtat("").page;
  return suivant;
}

/** De la vue « déjà classées » vers la file à traiter. */
export function versFileATraiter(etat: EtatClassees): EtatClassees {
  return changer(etat, "vue", VUE_A_TRAITER);
}
