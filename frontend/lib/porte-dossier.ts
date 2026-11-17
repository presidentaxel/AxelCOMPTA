/** Deux portes, un seul front (AXE-965).
 *
 * `compta.axelproject.fr` : vitrine et gestionnaire.
 * `app-compta.axelproject.fr` : la personne qui a un dossier. `/` y ouvre
 * son espace, jamais la vitrine. Les chemins publics sont `/dossier/…`.
 * Une ancienne adresse `/chauffeur/…` redirige vers la nouvelle.
 */

export const HOTE_DOSSIER = "app-compta.axelproject.fr";
export const HOTE_VITRINE = "compta.axelproject.fr";

export type DecisionPorte = { action: "continuer" } | { action: "rediriger"; url: string };

function nomHote(hote: string): string {
  const texte = hote.trim().toLowerCase();
  if (texte.startsWith("[")) return texte;
  return texte.split(":")[0] ?? "";
}

/** `/chauffeur/…` devient `/dossier/…`. `null` : ce n'est pas une ancienne adresse. */
export function cheminDossier(chemin: string): string | null {
  if (chemin === "/chauffeur") return "/dossier";
  if (chemin.startsWith("/chauffeur/")) return `/dossier${chemin.slice("/chauffeur".length)}`;
  return null;
}

function estCheminDossier(chemin: string): boolean {
  return chemin === "/dossier" || chemin.startsWith("/dossier/");
}

/** Où envoyer cette requête. `recherche` comprend le `?`, ou est vide. */
export function decisionPorte(hote: string, chemin: string, recherche: string): DecisionPorte {
  const nom = nomHote(hote);
  const ancien = cheminDossier(chemin);

  if (nom === HOTE_DOSSIER) {
    if (chemin === "/") return { action: "rediriger", url: `/dossier${recherche}` };
    if (ancien !== null) return { action: "rediriger", url: `${ancien}${recherche}` };
    return { action: "continuer" };
  }

  if (nom === HOTE_VITRINE && (ancien !== null || estCheminDossier(chemin))) {
    const cible = ancien ?? chemin;
    return { action: "rediriger", url: `https://${HOTE_DOSSIER}${cible}${recherche}` };
  }

  if (ancien !== null) return { action: "rediriger", url: `${ancien}${recherche}` };
  return { action: "continuer" };
}
