/** Où va une personne qui ouvre l'accueil (AXE-949).
 *
 * Sans session, la page publique reste affichée. Une personne déjà connectée
 * n'y voit pas la vitrine : elle arrive là où elle travaille. Le gestionnaire
 * l'emporte quand les deux sessions existent. Le jeton n'est lu que pour
 * choisir une page : la vérification est celle du serveur, à chaque appel. */

import { coteOuverte } from "./cote-connexion";

export type DestinationAccueil = "/portefeuille" | "/chauffeur" | null;

export type Jetons = { gestionnaire: string | null; chauffeur: string | null };

type Decoder = (jeton: string) => Record<string, unknown>;

function ouvre(jeton: string | null, cote: "gestionnaire" | "chauffeur", decoder: Decoder): boolean {
  if (!jeton) return false;
  try {
    return coteOuverte(decoder(jeton).app_metadata, cote) === cote;
  } catch {
    // Un jeton illisible est une session perdue : la vitrine s'affiche.
    return false;
  }
}

export function destinationAccueil(jetons: Jetons, decoder: Decoder): DestinationAccueil {
  if (ouvre(jetons.gestionnaire, "gestionnaire", decoder)) return "/portefeuille";
  if (ouvre(jetons.chauffeur, "chauffeur", decoder)) return "/chauffeur";
  return null;
}
