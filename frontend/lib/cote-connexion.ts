/** Quel côté une connexion a le droit d'ouvrir (AXE-822).
 *
 * Le formulaire qui envoie le lien dit le côté (`?cote=`). Un chauffeur
 * sans portefeuille n'ouvre pas le gestionnaire. Un gestionnaire sans
 * dossier n'ouvre pas l'espace chauffeur. Un compte qui porte les deux
 * (doc 03 §7), y compris le compte de test qui a aussi le portefeuille,
 * n'ouvre que le côté demandé. */

import { ROLE_LECTEUR_TEST } from "./compte-de-test";

export type Cote = "chauffeur" | "gestionnaire";

type Metadata = { dossier_id?: unknown; tenant_id?: unknown; role_test?: unknown };

function metadata(appMetadata: unknown): Metadata {
  return (appMetadata ?? {}) as Metadata;
}

function present(valeur: unknown): boolean {
  return typeof valeur === "string" && valeur !== "";
}

export function coteDemandee(recherche: string): Cote | null {
  const cote = new URLSearchParams(recherche).get("cote");
  return cote === "chauffeur" || cote === "gestionnaire" ? cote : null;
}

/** `interdit` : le formulaire n'est pas celui de ce compte. `sans_lien` :
 * le jeton n'ouvre aucun des deux espaces. */
export function coteOuverte(
  appMetadata: unknown,
  demandee: Cote | null,
): Cote | "interdit" | "sans_lien" {
  const meta = metadata(appMetadata);
  if (meta.role_test === ROLE_LECTEUR_TEST) {
    if (demandee === "gestionnaire") return present(meta.tenant_id) ? "gestionnaire" : "interdit";
    return "chauffeur";
  }
  const chauffeur = present(meta.dossier_id);
  const gestionnaire = present(meta.tenant_id);
  if (!chauffeur && !gestionnaire) return "sans_lien";
  if (demandee === "chauffeur") return chauffeur ? "chauffeur" : "interdit";
  if (demandee === "gestionnaire") return gestionnaire ? "gestionnaire" : "interdit";
  if (chauffeur && gestionnaire) return "chauffeur";
  return chauffeur ? "chauffeur" : "gestionnaire";
}
