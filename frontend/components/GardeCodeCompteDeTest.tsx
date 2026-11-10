"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect } from "react";

import { decoderChargeUtileJwt, obtenirSession } from "@/lib/auth-chauffeur";
import { deconnecterGestionnaire } from "@/lib/auth-gestionnaire";
import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "@/lib/mfa-code";

const PAGES_PUBLIQUES = new Set(["/chauffeur/login", "/chauffeur/accepter-invitation"]);

/** Le compte de test lit tous les dossiers : le code est exigé avant.
 * Entrer de ce côté ferme aussi la session gestionnaire. */
export function GardeCodeCompteDeTest() {
  const chemin = usePathname();

  useLayoutEffect(() => {
    if (PAGES_PUBLIQUES.has(chemin)) return;
    const session = obtenirSession();
    if (!session?.lecteurTest) return;
    deconnecterGestionnaire();
    let codeDejaSaisi = false;
    try {
      codeDejaSaisi = decoderChargeUtileJwt(session.accessToken).aal === "aal2";
    } catch {
      codeDejaSaisi = false;
    }
    if (codeDejaSaisi) return;
    const params = new URLSearchParams({ cote: "chauffeur", retour: chemin || "/chauffeur/test" });
    window.location.replace(`${CHEMIN_DOUBLE_AUTHENTIFICATION}?${params.toString()}`);
  }, [chemin]);

  return null;
}
