/** Ouvre la session qui correspond au jeton reçu dans un lien Supabase.
 * Le côté est celui du formulaire (`?cote=`). Un compte aux deux accès
 * n'ouvre que celui-là. Passer côté chauffeur ferme la session gestionnaire
 * du compte de test. */

import {
  decoderChargeUtileJwt,
  enregistrerSessionChauffeur,
  ErreurAuthChauffeur,
} from "./auth-chauffeur";
import {
  deconnecterGestionnaire,
  ErreurAuthGestionnaire,
  ouvrirSessionGestionnaire,
} from "./auth-gestionnaire";
import { cheminDuDossier, liensDuJeton } from "./compte-de-test";
import { coteOuverte, type Cote } from "./cote-connexion";
import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "./mfa-code";
import {
  MESSAGE_ESPACE_CHAUFFEUR,
  MESSAGE_ESPACE_GESTIONNAIRE,
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

/** Le lien d'invitation est le même pour les deux rôles. Le côté vient du
 * compte : un chauffeur, compte de test compris, ne passe pas par la page
 * gestionnaire. */
export function pageInvitation(accessToken: string): "chauffeur" | "gestionnaire" {
  const charge = decoderChargeUtileJwt(accessToken);
  const cote = coteOuverte(charge.app_metadata, null);
  if (cote === "chauffeur" || cote === "gestionnaire") return cote;
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

export function ouvrirSessionDepuisJetons(
  accessToken: string,
  refreshToken: string,
  demandee: Cote | null,
): string {
  const charge = decoderChargeUtileJwt(accessToken);
  const cote = coteOuverte(charge.app_metadata, demandee);
  const email = typeof charge.email === "string" ? charge.email : "";
  if (cote === "interdit") {
    throw new ErreurAuthChauffeur(
      demandee === "gestionnaire" ? MESSAGE_ESPACE_CHAUFFEUR : MESSAGE_ESPACE_GESTIONNAIRE,
    );
  }
  if (cote === "chauffeur") {
    const liens = liensDuJeton(charge.app_metadata);
    if (!liens) throw new ErreurAuthChauffeur(MESSAGE_SANS_LIEN);
    if (liens.lecteurTest || coteOuverte(charge.app_metadata, "gestionnaire") !== "gestionnaire") {
      deconnecterGestionnaire();
    }
    enregistrerSessionChauffeur({
      accessToken,
      refreshToken,
      dossierId: liens.dossierId,
      lecteurTest: liens.lecteurTest,
      email,
    });
    return cheminApresChauffeur(accessToken, liens);
  }
  if (cote === "gestionnaire") {
    try {
      ouvrirSessionGestionnaire(accessToken, refreshToken, email);
    } catch (exception) {
      throw new ErreurAuthGestionnaire(traduireExceptionAuth(exception));
    }
    return "/";
  }
  throw new ErreurAuthChauffeur(MESSAGE_SANS_LIEN);
}

/** Le compte de test saisit son code avant de voir un dossier. Les autres
 * chauffeurs vont directement à leur espace. */
export function cheminApresChauffeur(
  accessToken: string,
  liens: { dossierId: string; lecteurTest?: boolean },
): string {
  const chemin = cheminDuDossier(liens);
  if (!liens.lecteurTest) return chemin;
  const charge = decoderChargeUtileJwt(accessToken);
  if (charge.aal === "aal2") return chemin;
  const params = new URLSearchParams({ cote: "chauffeur", retour: chemin });
  return `${CHEMIN_DOUBLE_AUTHENTIFICATION}?${params.toString()}`;
}
