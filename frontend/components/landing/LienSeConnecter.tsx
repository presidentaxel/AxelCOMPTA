"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MouseEvent } from "react";

import { destinationAccueil } from "@/lib/accueil";
import { decoderChargeUtileJwt } from "@/lib/auth-chauffeur";
import { obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";

/** « Se connecter » depuis la vitrine : le portefeuille si une session
 * gestionnaire est ouverte, sinon la page de connexion. Une session
 * chauffeur ne change pas ce lien. La vitrine elle-même ne redirige pas. */
export function LienSeConnecter({ className }: { className: string }) {
  const routeur = useRouter();

  function ouvrir(event: MouseEvent<HTMLAnchorElement>) {
    const destination = destinationAccueil(
      { gestionnaire: obtenirSessionGestionnaire()?.accessToken ?? null },
      decoderChargeUtileJwt,
    );
    if (!destination) return;
    event.preventDefault();
    routeur.push(destination);
  }

  return (
    <Link href="/connexion" onClick={ouvrir} className={className}>
      Se connecter
    </Link>
  );
}
