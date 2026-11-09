/** Double authentification (AXE-812) : MFA native de Supabase, appels REST
 * directs (pas de SDK, ADR-003). Un code TOTP vérifié donne une session
 * `aal2`, que l'API exige pour l'admin. Pas de codes de secours natifs : un
 * autre admin réinitialise, et c'est tracé. */

import { enTetesSupabase, URL_SUPABASE } from "./auth-chauffeur";

import { imageDuQr, type Facteur } from "./mfa-code";

export { codeNormalise, facteurVerifie, imageDuQr, type Facteur } from "./mfa-code";
export type Enrolement = { facteurId: string; qrCode: string; secret: string };
export type Jetons = { accessToken: string; refreshToken: string };

async function corpsOuErreur<T>(reponse: Response, repli: string): Promise<T> {
  const corps = (await reponse.json().catch(() => ({}))) as Record<string, unknown>;
  if (!reponse.ok) {
    const message = typeof corps.msg === "string" ? corps.msg : repli;
    throw new Error(message);
  }
  return corps as T;
}

export async function lireFacteurs(accessToken: string): Promise<Facteur[]> {
  const reponse = await fetch(`${URL_SUPABASE}/auth/v1/user`, {
    headers: enTetesSupabase(accessToken),
  });
  const utilisateur = await corpsOuErreur<{ factors?: Facteur[] }>(
    reponse,
    "Impossible de lire votre compte.",
  );
  return utilisateur.factors ?? [];
}

/** Un nouveau facteur. Un enrôlement laissé en plan (non vérifié) est
 * d'abord retiré : Supabase refuserait le doublon. */
export async function enroler(accessToken: string, facteurs: readonly Facteur[]): Promise<Enrolement> {
  for (const facteur of facteurs) {
    if (facteur.factor_type === "totp" && facteur.status !== "verified") {
      await fetch(`${URL_SUPABASE}/auth/v1/factors/${facteur.id}`, {
        method: "DELETE",
        headers: enTetesSupabase(accessToken),
      });
    }
  }
  const reponse = await fetch(`${URL_SUPABASE}/auth/v1/factors`, {
    method: "POST",
    headers: enTetesSupabase(accessToken),
    body: JSON.stringify({ factor_type: "totp", friendly_name: "AxeLCompta" }),
  });
  const corps = await corpsOuErreur<{ id: string; totp: { qr_code: string; secret: string } }>(
    reponse,
    "Impossible de préparer la double authentification.",
  );
  return {
    facteurId: corps.id,
    qrCode: imageDuQr(corps.totp.qr_code),
    secret: corps.totp.secret,
  };
}

/** Défi puis vérification du code : renvoie les jetons `aal2`. */
export async function verifierCode(
  accessToken: string,
  facteurId: string,
  code: string,
): Promise<Jetons> {
  const defi = await corpsOuErreur<{ id: string }>(
    await fetch(`${URL_SUPABASE}/auth/v1/factors/${facteurId}/challenge`, {
      method: "POST",
      headers: enTetesSupabase(accessToken),
    }),
    "Impossible de vérifier le code.",
  );
  const session = await corpsOuErreur<{ access_token: string; refresh_token: string }>(
    await fetch(`${URL_SUPABASE}/auth/v1/factors/${facteurId}/verify`, {
      method: "POST",
      headers: enTetesSupabase(accessToken),
      body: JSON.stringify({ challenge_id: defi.id, code }),
    }),
    "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.",
  );
  return { accessToken: session.access_token, refreshToken: session.refresh_token };
}
