/** Ouvre la session qui correspond au jeton reçu dans un lien Supabase.
 * Le côté est celui du formulaire (`?cote=`). Un compte aux deux accès
 * n'ouvre que celui-là. Passer côté chauffeur ferme la session gestionnaire
 * du compte de test. */

import {
  decoderChargeUtileJwt,
  enTetesSupabase,
  enregistrerSessionChauffeur,
  ErreurAuthChauffeur,
  extraireErreurSupabase,
  URL_SUPABASE,
} from "./auth-chauffeur";
import {
  deconnecterGestionnaire,
  ErreurAuthGestionnaire,
  ouvrirSessionGestionnaire,
} from "./auth-gestionnaire";
import { cheminDuDossier, liensDuJeton } from "./compte-de-test";
import { coteDemandee, coteOuverte, type Cote } from "./cote-connexion";
import { coteMemorisee } from "./destination-lien";
import { CHEMIN_DOUBLE_AUTHENTIFICATION } from "./mfa-code";
import {
  MESSAGE_ESPACE_CHAUFFEUR,
  MESSAGE_ESPACE_GESTIONNAIRE,
  MESSAGE_LIEN_EXPIRE,
  MESSAGE_LIEN_INCOMPLET,
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

const TYPES_JETON = new Set(["signup", "invite", "magiclink", "recovery", "email_change", "email"]);

const echanges = new Map<string, Promise<FragmentAuth>>();

async function appelerVerify(tokenHash: string, type: string): Promise<FragmentAuth> {
  if (!TYPES_JETON.has(type)) throw new ErreurAuthChauffeur(MESSAGE_LIEN_EXPIRE);
  let reponse: Response;
  try {
    reponse = await fetch(`${URL_SUPABASE}/auth/v1/verify`, {
      method: "POST",
      headers: enTetesSupabase(),
      body: JSON.stringify({ token_hash: tokenHash, type }),
    });
  } catch (exception) {
    throw new ErreurAuthChauffeur(traduireExceptionAuth(exception));
  }
  if (!reponse.ok) await extraireErreurSupabase(reponse);
  const corps = (await reponse.json().catch(() => ({}))) as {
    access_token?: string;
    refresh_token?: string;
    session?: { access_token?: string; refresh_token?: string };
  };
  const session = corps.session ?? corps;
  if (!session.access_token || !session.refresh_token) {
    throw new ErreurAuthChauffeur(MESSAGE_LIEN_EXPIRE);
  }
  return { accessToken: session.access_token, refreshToken: session.refresh_token, type };
}

/** Un seul échange par jeton : React relance l'effet en développement, et
 * Supabase refuse le second appel (« déjà ouvert »). */
export function echangerJetonHash(tokenHash: string, type: string): Promise<FragmentAuth> {
  const cle = `${type}\n${tokenHash}`;
  const deja = echanges.get(cle);
  if (deja) return deja;
  const promesse = appelerVerify(tokenHash, type).catch((exception: unknown) => {
    echanges.delete(cle);
    throw exception;
  });
  echanges.set(cle, promesse);
  return promesse;
}

function deposerFragment(recu: FragmentAuth): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("token_hash");
  const hash = new URLSearchParams({
    access_token: recu.accessToken,
    refresh_token: recu.refreshToken,
    type: recu.type,
  });
  url.hash = hash.toString();
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

/** Lit le lien ouvert dans cet onglet. `token_hash` vient du courriel : on
 * l'échange ici, un logiciel de messagerie qui ne fait qu'ouvrir l'adresse
 * ne consomme pas le jeton. Le côté est celui de l'adresse, sinon celui
 * mémorisé quand le formulaire a demandé le lien. */
export async function lireLienCourant(): Promise<{ fragment: FragmentAuth; cote: Cote | null }> {
  const recherche = new URLSearchParams(window.location.search);
  const cote = coteDemandee(recherche.toString()) ?? coteMemorisee();
  const message = messageParametresAuth(recherche);
  if (message) throw new ErreurAuthChauffeur(message);
  const tokenHash = recherche.get("token_hash");
  const type = recherche.get("type");
  if (tokenHash && type && !window.location.hash.includes("access_token=")) {
    const recu = await echangerJetonHash(tokenHash, type);
    deposerFragment(recu);
    return { fragment: recu, cote };
  }
  if (recherche.get("code") && !window.location.hash.includes("access_token=")) {
    throw new ErreurAuthChauffeur(MESSAGE_LIEN_INCOMPLET);
  }
  return { fragment: lireFragmentAuth(window.location.hash), cote };
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
