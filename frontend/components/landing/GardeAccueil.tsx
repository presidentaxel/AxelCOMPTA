"use client";

import { useRouter } from "next/navigation";
import { useLayoutEffect } from "react";

import { destinationAccueil } from "@/lib/accueil";
import { decoderChargeUtileJwt, obtenirSession } from "@/lib/auth-chauffeur";
import { obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";

/** Une personne déjà connectée ne voit pas la vitrine : le gestionnaire va au
 * portefeuille, le chauffeur dans son espace. La session vit dans le
 * navigateur : le serveur ne peut pas la lire, la page publique est donc
 * servie d'abord, puis cette garde redirige avant la première peinture
 * quand le script est chargé. Sans session, elle ne fait rien. */
export function GardeAccueil() {
  const routeur = useRouter();

  useLayoutEffect(() => {
    const destination = destinationAccueil(
      {
        gestionnaire: obtenirSessionGestionnaire()?.accessToken ?? null,
        chauffeur: obtenirSession()?.accessToken ?? null,
      },
      decoderChargeUtileJwt,
    );
    if (destination) routeur.replace(destination);
  }, [routeur]);

  return null;
}
