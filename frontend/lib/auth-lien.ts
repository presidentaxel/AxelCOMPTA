/** Ouvre la session qui correspond au jeton reçu dans un lien Supabase.
 * Un compte chauffeur porte `dossier_id`, un compte gestionnaire `tenant_id`.
 */

import {
  decoderChargeUtileJwt,
  enregistrerSessionChauffeur,
  ErreurAuthChauffeur,
} from "./auth-chauffeur";
import { ErreurAuthGestionnaire, ouvrirSessionGestionnaire } from "./auth-gestionnaire";
import {
  MESSAGE_LIEN_EXPIRE,
  MESSAGE_SANS_LIEN,
  messageParametresAuth,
  traduireExceptionAuth,
} from "./messages-auth";

export type FragmentAuth = {
  accessToken: string;
  refreshToken: string;
  type: string;
};

export function estLienInvitation(fragment: string): boolean {
  return new URLSearchParams(fragment.replace(/^#/, "")).get("type") === "invite";
}

/** Le lien d'invitation est le même pour les deux rôles. Le chauffeur a un
 * `dossier_id`, le membre d'équipe un `tenant_id`. */
export function pageInvitation(accessToken: string): "chauffeur" | "gestionnaire" {
  const charge = decoderChargeUtileJwt(accessToken);
  const meta = (charge.app_metadata ?? {}) as { dossier_id?: string; tenant_id?: string };
  if (meta.dossier_id) return "chauffeur";
  if (meta.tenant_id) return "gestionnaire";
  throw new ErreurAuthChauffeur(MESSAGE_SANS_LIEN);
}

export function lireFragmentAuth(fragment: string): FragmentAuth {
  const parametres = new URLSearchParams(fragment.replace(/^#/, ""));
  const message = messageParametresAuth(parametres);
  if (message) throw new ErreurAuthChauffeur(message);
  const accessToken = parametres.get("access_token");
  const refreshToken = parametres.get("refresh_token");
  if (!accessToken || !refreshToken) {
    throw new ErreurAuthChauffeur(MESSAGE_LIEN_EXPIRE);
  }
  return { accessToken, refreshToken, type: parametres.get("type") ?? "" };
}

export function ouvrirSessionDepuisJetons(accessToken: string, refreshToken: string): string {
  const charge = decoderChargeUtileJwt(accessToken);
  const meta = (charge.app_metadata ?? {}) as { dossier_id?: string; tenant_id?: string };
  const email = typeof charge.email === "string" ? charge.email : "";
  if (meta.dossier_id) {
    enregistrerSessionChauffeur({
      accessToken,
      refreshToken,
      dossierId: meta.dossier_id,
      email,
    });
    return `/chauffeur/${meta.dossier_id}`;
  }
  if (meta.tenant_id) {
    try {
      ouvrirSessionGestionnaire(accessToken, refreshToken, email);
    } catch (exception) {
      throw new ErreurAuthGestionnaire(traduireExceptionAuth(exception));
    }
    return "/";
  }
  throw new ErreurAuthChauffeur(MESSAGE_SANS_LIEN);
}
