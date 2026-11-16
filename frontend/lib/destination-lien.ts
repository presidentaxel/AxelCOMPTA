/** Où déposer un lien Supabase quand il n'arrive pas sur sa page.
 *
 * Le tableau de bord n'accepte un `redirect_to` que s'il est identique à
 * une URL autorisée. Sinon le lien retombe sur l'adresse du site, avec les
 * jetons dans le fragment. L'accueil envoie alors vers `/portefeuille`, et
 * la session absente ne doit pas effacer ce fragment. */

import { coteOuverte, type Cote } from "./cote-connexion";

const CLE_COTE = "axelcompta_cote_lien";

/** Le formulaire qui demande le lien. Le `redirect_to` reste sans paramètre,
 * pour coller à l'URL autorisée ; le côté est relu au retour, sur ce
 * navigateur. */
export function memoriserCoteLien(cote: Cote): void {
  try {
    window.sessionStorage.setItem(CLE_COTE, cote);
  } catch {
    // Le jeton suffit quand le compte n'a qu'un côté.
  }
}

export function coteMemorisee(): Cote | null {
  try {
    const cote = window.sessionStorage.getItem(CLE_COTE);
    return cote === "chauffeur" || cote === "gestionnaire" ? cote : null;
  } catch {
    return null;
  }
}

function parametres(fragment: string): URLSearchParams {
  return new URLSearchParams(fragment.replace(/^#/, ""));
}

export function fragmentPorteUnLien(fragment: string): boolean {
  const recu = parametres(fragment);
  return (
    recu.has("access_token") ||
    recu.has("error") ||
    recu.has("error_code") ||
    recu.has("error_description")
  );
}

function recherchePorteUnLien(recherche: string): boolean {
  const recu = new URLSearchParams(recherche);
  return (
    recu.has("code") || recu.has("error") || recu.has("error_code") || recu.has("error_description")
  );
}

function coteDansRecherche(recherche: string): string {
  const cote = new URLSearchParams(recherche).get("cote");
  if (cote !== "chauffeur" && cote !== "gestionnaire") return "";
  return `?cote=${cote}`;
}

function chargeUtile(jeton: string): Record<string, unknown> | null {
  const partie = jeton.split(".")[1];
  if (!partie) return null;
  try {
    const normalise = partie.replace(/-/g, "+").replace(/_/g, "/");
    const complete = normalise + "=".repeat((4 - (normalise.length % 4)) % 4);
    return JSON.parse(atob(complete)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function pageCourante(chemin: string): boolean {
  return chemin === "/auth/lien" || chemin.startsWith("/chauffeur/accepter-invitation");
}

/** Page qui doit recevoir le lien. `null` : rien à reprendre, ou la page
 * courante s'en charge déjà. */
export function destinationLienAuth(
  chemin: string,
  recherche: string,
  fragment: string,
): string | null {
  if (pageCourante(chemin)) return null;
  if (recherchePorteUnLien(recherche) && !fragmentPorteUnLien(fragment)) {
    const query = recherche.startsWith("?") || recherche.length === 0 ? recherche : `?${recherche}`;
    return `/auth/lien${query}`;
  }
  if (!fragmentPorteUnLien(fragment)) return null;
  const recu = parametres(fragment);
  const jeton = recu.get("access_token");
  if (recu.get("type") === "invite" && jeton) {
    const charge = chargeUtile(jeton);
    if (charge && coteOuverte(charge.app_metadata, null) === "chauffeur") {
      return `/chauffeur/accepter-invitation${fragment}`;
    }
  }
  return `/auth/lien${coteDansRecherche(recherche)}${fragment}`;
}

export type RepriseLien = { action: "rediriger"; url: string } | { action: "rester" } | { action: "aucune" };

/** `rester` : le fragment est là et la page courante doit le lire.
 * Une redirection vers la connexion l'effacerait. */
export function repriseLienAuth(chemin: string, recherche: string, fragment: string): RepriseLien {
  const cible = destinationLienAuth(chemin, recherche, fragment);
  if (cible) return { action: "rediriger", url: cible };
  if (fragmentPorteUnLien(fragment) || recherchePorteUnLien(recherche)) return { action: "rester" };
  return { action: "aucune" };
}
