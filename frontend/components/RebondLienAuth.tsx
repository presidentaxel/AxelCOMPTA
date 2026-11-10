"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { estLienInvitation, lireFragmentAuth, pageInvitation } from "@/lib/auth-lien";

/** Si Supabase renvoie le lien vers la racine du site, le fragment
 * `#access_token` est repris. Une invitation chauffeur va choisir son mot
 * de passe sur sa page, une invitation d'équipe sur `/auth/lien`.
 * `location.replace` garde le fragment : le routeur Next le perd. */
export function RebondLienAuth() {
  const chemin = usePathname();

  useEffect(() => {
    if (chemin === "/auth/lien" || chemin.startsWith("/chauffeur/accepter-invitation")) {
      return;
    }
    const fragment = window.location.hash;
    if (!fragment.includes("access_token=")) {
      return;
    }
    const cible = destinationDuFragment(fragment, window.location.search);
    window.location.replace(cible);
  }, [chemin]);

  return null;
}

function destinationDuFragment(fragment: string, recherche: string): string {
  const cote = recherche.includes("cote=") ? recherche : "";
  if (!estLienInvitation(fragment)) return `/auth/lien${cote}${fragment}`;
  try {
    const recu = lireFragmentAuth(fragment);
    if (pageInvitation(recu.accessToken) === "chauffeur") {
      return `/chauffeur/accepter-invitation${fragment}`;
    }
  } catch {
    // Jeton illisible : la page du lien affiche l'erreur.
  }
  return `/auth/lien${cote}${fragment}`;
}
