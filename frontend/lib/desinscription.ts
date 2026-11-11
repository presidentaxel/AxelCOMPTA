/** Ce que la page de désinscription (AXE-808) dit, selon la réponse de l'API.
 * Les trois phrases sont celles de la page d'origine ; seul le statut est
 * nouveau : il permet à l'écran de distinguer attente, succès et refus. */

export type EtatDesinscription = {
  statut: "attente" | "faite" | "refusee" | "injoignable";
  message: string;
};

export const ETAT_ATTENTE: EtatDesinscription = { statut: "attente", message: "Enregistrement…" };

export const ETAT_INJOIGNABLE: EtatDesinscription = {
  statut: "injoignable",
  message: "Le serveur ne répond pas. Réessayez dans un instant.",
};

/** L'API répond `{ message }` au succès et `{ detail }` au refus ; un corps
 * illisible tombe sur une phrase par défaut. `detail` n'est repris que s'il est
 * une phrase : sur un lien incomplet, FastAPI renvoie une liste d'erreurs de
 * validation, qui ne doit jamais arriver à l'écran. */
export function etatApresReponse(
  ok: boolean,
  corps: { message?: unknown; detail?: unknown },
): EtatDesinscription {
  const phrase = (valeur: unknown): string | null =>
    typeof valeur === "string" && valeur.trim() ? valeur : null;
  return ok
    ? { statut: "faite", message: phrase(corps.message) ?? "C'est noté." }
    : { statut: "refusee", message: phrase(corps.detail) ?? "Ce lien n'est pas valable." };
}
