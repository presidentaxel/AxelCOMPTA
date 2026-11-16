"use client";

import { useLayoutEffect } from "react";

import { decoderChargeUtileJwt } from "@/lib/auth-chauffeur";
import { deconnecterGestionnaire, obtenirSessionGestionnaire } from "@/lib/auth-gestionnaire";
import { coteOuverte } from "@/lib/cote-connexion";
import { repriseLienAuth } from "@/lib/destination-lien";
import { laisserMessageConnexion } from "@/lib/message-connexion";
import { MESSAGE_ESPACE_CHAUFFEUR } from "@/lib/messages-auth";

/** Un jeton chauffeur, ou de compte de test, ne doit jamais afficher le
 * côté gestionnaire. La session déjà stockée est effacée. */
export function GardeEspaceGestionnaire() {
  useLayoutEffect(() => {
    const reprise = repriseLienAuth(
      window.location.pathname,
      window.location.search,
      window.location.hash,
    );
    if (reprise.action === "rediriger") {
      window.location.replace(reprise.url);
      return;
    }
    if (reprise.action === "rester") return;
    const session = obtenirSessionGestionnaire();
    if (!session) return;
    let autorise = false;
    let chauffeur = false;
    try {
      const charge = decoderChargeUtileJwt(session.accessToken);
      const cote = coteOuverte(charge.app_metadata, "gestionnaire");
      autorise = cote === "gestionnaire";
      chauffeur = cote === "interdit";
    } catch {
      autorise = false;
    }
    if (autorise) return;
    if (chauffeur) laisserMessageConnexion(MESSAGE_ESPACE_CHAUFFEUR);
    deconnecterGestionnaire();
    window.location.replace("/connexion");
  }, []);

  return null;
}
