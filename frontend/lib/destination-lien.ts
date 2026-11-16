/** Où déposer un lien Supabase quand il n'arrive pas sur sa page.
 *
 * Le `redirect_to` porte le côté du formulaire (`?cote=`). Supabase compare
 * l'adresse sans cette query à la liste autorisée, puis la conserve. Si le
 * lien retombe quand même sur l'accueil, le fragment ou `token_hash` est
 * repris ici, avant que l'absence de session n'envoie vers la connexion.
 * Le côté est aussi gardé dans ce navigateur : le clic depuis l'e-mail
 * ouvre un autre onglet, qui n'a pas le sessionStorage de la demande. */

import { coteOuverte, type Cote } from "./cote-connexion";

const CLE_COTE = "axelcompta_cote_lien";

function coteStockee(stockage: Storage): Cote | null {
  const cote = stockage.getItem(CLE_COTE);
  return cote === "chauffeur" || cote === "gestionnaire" ? cote : null;
}

/** Le formulaire qui demande le lien. `localStorage` : le nouvel onglet de
 * l'e-mail le lit encore. `sessionStorage` : un onglet déjà ouvert, avant
 * ce changement. */
export function memoriserCoteLien(cote: Cote): void {
  try {
    window.localStorage.setItem(CLE_COTE, cote);
  } catch {
    // Le jeton suffit quand le compte n'a qu'un côté.
  }
  try {
    window.sessionStorage.setItem(CLE_COTE, cote);
  } catch {
    // idem
  }
}

export function coteMemorisee(): Cote | null {
  try {
    return coteStockee(window.localStorage) ?? coteStockee(window.sessionStorage);
  } catch {
    return null;
  }
}

/** Adresse exacte passée à Supabase. La query est le côté, ou `flux=compte`
 * pour le changement d'adresse : le courriel ajoute `&token_hash` derrière,
 * donc un `?` est toujours là. */
export function adresseRetourAuth(origin: string, cote?: Cote | null): string {
  const base = `${origin}/auth/lien`;
  if (cote === "chauffeur" || cote === "gestionnaire") return `${base}?cote=${cote}`;
  return `${base}?flux=compte`;
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
    recu.has("code") ||
    recu.has("token_hash") ||
    recu.has("error") ||
    recu.has("error_code") ||
    recu.has("error_description")
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
