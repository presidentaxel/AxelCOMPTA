/** Où « Se connecter » envoie un gestionnaire déjà connecté (AXE-949).
 *
 * La vitrine est celle des cabinets et des centrales. Le lien va au
 * portefeuille si une session gestionnaire est ouverte, sinon à
 * `/connexion`. Une session chauffeur ne compte pas : l'espace chauffeur
 * est une autre porte. Le jeton n'est lu que pour choisir la page. */

import { coteOuverte } from "./cote-connexion";

export type DestinationAccueil = "/portefeuille" | null;

export type Jetons = { gestionnaire: string | null };

type Decoder = (jeton: string) => Record<string, unknown>;

function ouvrePortefeuille(jeton: string | null, decoder: Decoder): boolean {
  if (!jeton) return false;
  try {
    return coteOuverte(decoder(jeton).app_metadata, "gestionnaire") === "gestionnaire";
  } catch {
    // Un jeton illisible ne compte pas comme une session ouverte.
    return false;
  }
}

export function destinationAccueil(jetons: Jetons, decoder: Decoder): DestinationAccueil {
  if (ouvrePortefeuille(jetons.gestionnaire, decoder)) return "/portefeuille";
  return null;
}
