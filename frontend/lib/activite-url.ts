/** Onglet, mois et sens de l'écran Activité, portés par l'URL.
 * Les valeurs par défaut n'apparaissent pas : l'adresse reste courte, et
 * revenir sur l'écran sans query retrouve le dernier choix mémorisé. */

export type VueActivite = "traiter" | "mouvements";
export type SensActivite = "sorties" | "entrees";

export type EtatActivite = {
  vue: VueActivite;
  mois: string | null;
  sens: SensActivite;
};

const MOIS = /^\d{4}-(0[1-9]|1[0-2])$/;
const CLE = "axelcompta_activite";

export const EVENEMENT_ACTIVITE = "axelcompta:activite";

export function lireEtatActivite(params: URLSearchParams): EtatActivite {
  const mois = params.get("mois");
  return {
    vue: params.get("vue") === "mouvements" ? "mouvements" : "traiter",
    mois: mois !== null && MOIS.test(mois) ? mois : null,
    sens: params.get("sens") === "entrees" ? "entrees" : "sorties",
  };
}

/** Query à poser, sans les valeurs par défaut. Les autres paramètres restent. */
export function ecrireEtatActivite(actuel: URLSearchParams, maj: Partial<EtatActivite>): string {
  const etat: EtatActivite = { ...lireEtatActivite(actuel), ...maj };
  const suivant = new URLSearchParams(actuel.toString());
  poser(suivant, "vue", etat.vue === "mouvements" ? "mouvements" : null);
  poser(suivant, "mois", etat.mois);
  poser(suivant, "sens", etat.sens === "entrees" ? "entrees" : null);
  return suivant.toString();
}

export function memoriserActivite(dossierId: string, requete: string): void {
  try {
    const cle = `${CLE}:${dossierId}`;
    if (requete) window.sessionStorage.setItem(cle, requete);
    else window.sessionStorage.removeItem(cle);
  } catch {
    // Navigation privée : l'URL seule garde l'onglet.
  }
  window.dispatchEvent(new Event(EVENEMENT_ACTIVITE));
}

export function relireActivite(dossierId: string): string {
  try {
    return window.sessionStorage.getItem(`${CLE}:${dossierId}`) ?? "";
  } catch {
    return "";
  }
}

function poser(params: URLSearchParams, cle: string, valeur: string | null): void {
  if (valeur) params.set(cle, valeur);
  else params.delete(cle);
}
