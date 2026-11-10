/** Appels authentifiés à l'API, communs au chauffeur et au gestionnaire.
 *
 * Le jeton d'accès Supabase expire au bout d'une heure environ. Avant, rien
 * ne le renouvelait : passé ce délai, chaque appel répondait 401 et la page
 * restait affichée avec une erreur rouge. Ici :
 * - le jeton est renouvelé (jeton de rafraîchissement) un peu avant son
 *   expiration, et une fois de plus si l'API répond quand même 401 ;
 * - si le renouvellement échoue, la session est effacée et l'utilisateur
 *   renvoyé vers sa page de connexion, avec le motif et la page à retrouver ;
 * - un serveur injoignable donne un message clair, pas une erreur technique.
 */

import { ApiError } from "./api";
import { messageConnexionEnAttente } from "./message-connexion";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
// Renouveler avant l'échéance : l'horloge du poste et le trajet réseau.
const MARGE_EXPIRATION_S = 60;
export const MESSAGE_SERVEUR_INJOIGNABLE =
  "Le serveur ne répond pas. Vérifiez votre connexion, puis réessayez dans un instant.";

export class SessionExpiree extends Error {}

type Jetons = { accessToken: string; refreshToken: string };

export type EspaceAuthentifie<S extends Jetons> = {
  lire: () => S | null;
  /** Les nouveaux jetons, le reste de la session inchangé. */
  enregistrer: (session: S) => void;
  effacer: () => void;
  pageConnexion: string;
};

function expireBientot(accessToken: string): boolean {
  const partie = accessToken.split(".")[1];
  if (!partie) return true;
  try {
    const charge = JSON.parse(atob(partie.replace(/-/g, "+").replace(/_/g, "/"))) as {
      exp?: number;
    };
    return typeof charge.exp !== "number" || charge.exp - Date.now() / 1000 < MARGE_EXPIRATION_S;
  } catch {
    return true;
  }
}

async function jetonsRenouveles(refreshToken: string): Promise<Jetons | null> {
  try {
    const reponse = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: { apikey: SUPABASE_ANON_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!reponse.ok) return null;
    const corps = (await reponse.json()) as { access_token?: string; refresh_token?: string };
    if (!corps.access_token || !corps.refresh_token) return null;
    return { accessToken: corps.access_token, refreshToken: corps.refresh_token };
  } catch {
    return null;
  }
}

// Un seul renouvellement à la fois : Supabase fait tourner le jeton de
// rafraîchissement, deux appels simultanés en useraient un déjà consommé.
const enCours = new Map<string, Promise<boolean>>();

async function renouveler<S extends Jetons>(espace: EspaceAuthentifie<S>): Promise<boolean> {
  const cle = espace.pageConnexion;
  const existant = enCours.get(cle);
  if (existant) return existant;
  const promesse = (async () => {
    const session = espace.lire();
    if (!session) return false;
    const jetons = await jetonsRenouveles(session.refreshToken);
    if (!jetons) return false;
    espace.enregistrer({ ...session, ...jetons });
    return true;
  })();
  enCours.set(cle, promesse);
  try {
    return await promesse;
  } finally {
    enCours.delete(cle);
  }
}

/** Efface la session et quitte la page interne pour la page de connexion. */
export function renvoyerVersConnexion<S extends Jetons>(espace: EspaceAuthentifie<S>): never {
  espace.effacer();
  if (typeof window !== "undefined") {
    const retour = window.location.pathname + window.location.search;
    const parametres = new URLSearchParams({ session: "expiree", retour });
    window.location.replace(`${espace.pageConnexion}?${parametres.toString()}`);
  }
  throw new SessionExpiree("Votre session a expiré. Reconnectez-vous.");
}

async function envoyer(url: string, init: RequestInit, accessToken: string): Promise<Response> {
  const entetes = new Headers(init.headers);
  entetes.set("Authorization", `Bearer ${accessToken}`);
  try {
    return await fetch(url, { ...init, headers: entetes, cache: "no-store" });
  } catch {
    throw new ApiError(MESSAGE_SERVEUR_INJOIGNABLE, 0);
  }
}

/** Requête authentifiée. Ne renvoie jamais un 401 : soit la session est
 * renouvelée et la requête rejouée, soit l'utilisateur part vers la
 * connexion. Les autres statuts sont rendus tels quels à l'appelant. */
export async function appelAuthentifie<S extends Jetons>(
  espace: EspaceAuthentifie<S>,
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  let session = espace.lire();
  if (!session) {
    // La garde a déjà envoyé vers la connexion : un second renvoi écraserait
    // le message qui dit pourquoi.
    if (messageConnexionEnAttente()) throw new SessionExpiree(messageConnexionEnAttente() ?? "");
    renvoyerVersConnexion(espace);
  }
  if (expireBientot(session.accessToken) && (await renouveler(espace))) {
    session = espace.lire() ?? session;
  }
  const reponse = await envoyer(url, init, session.accessToken);
  if (reponse.status !== 401) return reponse;
  if (!(await renouveler(espace))) renvoyerVersConnexion(espace);
  const renouvelee = espace.lire();
  if (!renouvelee) renvoyerVersConnexion(espace);
  const rejouee = await envoyer(url, init, renouvelee.accessToken);
  if (rejouee.status === 401) renvoyerVersConnexion(espace);
  return rejouee;
}

/** Corps JSON d'une réponse, ou `{}` si le serveur a répondu autre chose
 * (une page d'erreur texte, par exemple). */
export async function lireCorps(reponse: Response): Promise<unknown> {
  try {
    return (await reponse.json()) as unknown;
  } catch {
    return {};
  }
}

export const MESSAGE_ERREUR_SERVEUR = "Erreur du serveur. Réessayez dans un instant.";

/** Le message d'erreur de l'API (`detail`), sinon le statut. */
export function erreurApi(corps: unknown, reponse: Response): ApiError {
  const valeur =
    typeof corps === "object" && corps !== null ? (corps as { detail?: unknown }).detail : null;
  const detail = typeof valeur === "string" ? valeur : null;
  return new ApiError(
    detail ?? (reponse.status >= 500 ? MESSAGE_ERREUR_SERVEUR : `HTTP ${reponse.status}`),
    reponse.status,
  );
}

/** Phrase à montrer quand un chargement échoue.
 * Le réseau (aucune réponse, `status` 0) et le serveur (5xx) ne disent pas
 * la même chose : un `.catch` qui les remplace par « Impossible de charger… »
 * avale le message utile. Un code technique (`HTTP 404`) non plus : on
 * retombe sur la phrase de repli de l'écran. */
export function messageEchecChargement(exception: unknown, repli: string): string {
  if (!(exception instanceof ApiError)) return repli;
  if (exception.status === 0) return MESSAGE_SERVEUR_INJOIGNABLE;
  if (exception.status >= 500) {
    return /^HTTP \d+$/.test(exception.message) ? MESSAGE_ERREUR_SERVEUR : exception.message;
  }
  return /^HTTP \d+$/.test(exception.message) ? repli : exception.message;
}

/** Retour après reconnexion : un chemin interne seulement, jamais une autre origine. */
export function cheminDeRetour(recherche: string, parDefaut: string): string {
  const retour = new URLSearchParams(recherche).get("retour");
  return retour && retour.startsWith("/") && !retour.startsWith("//") ? retour : parDefaut;
}

export function sessionAExpire(recherche: string): boolean {
  return new URLSearchParams(recherche).get("session") === "expiree";
}
