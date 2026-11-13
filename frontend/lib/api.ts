import type { DocumentCloture } from "./types";

// Erreur typée plutôt qu'un message générique : le composant appelant
// affiche `detail` tel quel (400 catégorie inconnue, 409 déjà tranchée,
// doc 17 §9 bloc C) au lieu d'un "une erreur est survenue" muet.
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

// doc 19 §8bis (2026-09-11) : ces routes exigent désormais un jeton indiv
// (api/routes.py) — un `<a href>` ne peut porter d'en-tête `Authorization`,
// donc ce ne sont plus des URLs complètes à mettre directement dans un
// lien, seulement des **chemins** pour `telechargerAvecAuthChauffeur`
// (lib/auth-chauffeur.ts), qui fait le fetch authentifié puis déclenche
// l'enregistrement via une URL d'objet temporaire.
export function cheminTelechargementCloture(dossierId: string, document: DocumentCloture): string {
  return `/dossiers/${dossierId}/${document}`;
}

// doc 20 : dossier de dépôt greffe/INPI — même logique, le PDF reflète
// automatiquement l'état signé/non signé côté serveur (api/routes.py).
export function cheminGreffeInpi(dossierId: string): string {
  return `/dossiers/${dossierId}/greffe-inpi.pdf`;
}
