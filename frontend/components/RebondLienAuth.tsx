"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect } from "react";

import { destinationLienAuth } from "@/lib/destination-lien";

/** Si Supabase renvoie le lien vers la racine du site, le fragment
 * `#access_token` est repris avant qu'une page interne ne le prenne pour
 * une session expirée. Une invitation chauffeur va choisir son mot de passe
 * sur sa page, une invitation d'équipe sur `/auth/lien`.
 * `location.replace` garde le fragment : le routeur Next le perd.
 * `useLayoutEffect` : avant les chargements, qui partent en `useEffect`. */
export function RebondLienAuth() {
  const chemin = usePathname();

  useLayoutEffect(() => {
    const cible = destinationLienAuth(chemin, window.location.search, window.location.hash);
    if (cible) window.location.replace(cible);
  }, [chemin]);

  return null;
}
