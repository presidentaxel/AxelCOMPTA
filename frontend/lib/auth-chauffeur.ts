/** Connexion et session chauffeur (doc 17 §9 bloc B, doc 19 §5.1-2).
 *
 * Appels REST directs à Supabase Auth — jamais le SDK
 * `@supabase/supabase-js`, même choix que le backend (`demo_comptes.py`,
 * appels `httpx` bruts) : cohérent avec la règle anti-lock-in d'ADR-003
 * (« n'utiliser que la connection string/API standard, jamais un SDK
 * propriétaire qui s'installe par défaut »). La clé anon est faite pour
 * être exposée côté client (contrairement à la service role key,
 * backend-only).
 *
 * Session stockée en `localStorage` — lectures/écritures protégées
 * (peut échouer en navigation privée ou si le viewer bloque le stockage
 * de site) : dans ce cas, on retombe simplement sur "pas de session",
 * jamais une exception qui casse la page.
 */

import { ApiError } from "./api";
import { appelAuthentifie, erreurApi, lireCorps } from "./session";
import type {
  AffectationVue,
  BulletinVue,
  DividendesVue,
  ClotureExerciceVue,
  ProvisionClotureVue,
  NotificationVue,
  SignatureGreffeVue,
  TransactionVue,
} from "./types";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
const CLE_SESSION = "axelcompta_session_chauffeur";

export type SessionChauffeur = {
  accessToken: string;
  refreshToken: string;
  dossierId: string;
  email: string;
};

export class ErreurAuthChauffeur extends Error {}

export const URL_SUPABASE = SUPABASE_URL;

export function enTetesSupabase(accessToken?: string): Record<string, string> {
  return {
    apikey: SUPABASE_ANON_KEY,
    Authorization: `Bearer ${accessToken ?? SUPABASE_ANON_KEY}`,
    "Content-Type": "application/json",
  };
}

/** Décodage du payload d'un JWT — **aucune vérification de signature**,
 * uniquement pour peupler l'URL après connexion. La vérification réelle
 * est côté serveur (`demo_auth.verifier_jwt`) à chaque appel API. */
export function decoderChargeUtileJwt(jeton: string): Record<string, unknown> {
  const partie = jeton.split(".")[1];
  if (!partie) {
    throw new ErreurAuthChauffeur("Lien invalide ou expiré.");
  }
  try {
    const normalise = partie.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalise)) as Record<string, unknown>;
  } catch {
    throw new ErreurAuthChauffeur("Lien invalide ou expiré.");
  }
}

function dossierIdDepuisJeton(accessToken: string): string {
  const charge = decoderChargeUtileJwt(accessToken);
  // `app_metadata` (écrit côté serveur), jamais `user_metadata` (modifiable
  // par l'utilisateur) : voir demo_auth.py.
  const metadata = charge.app_metadata as { dossier_id?: string } | undefined;
  const dossierId = metadata?.dossier_id;
  if (!dossierId) {
    throw new ErreurAuthChauffeur("Ce compte n'est lié à aucun dossier.");
  }
  return dossierId;
}

export function obtenirSession(): SessionChauffeur | null {
  try {
    const brut = window.localStorage.getItem(CLE_SESSION);
    return brut ? (JSON.parse(brut) as SessionChauffeur) : null;
  } catch {
    return null;
  }
}

export function enregistrerSessionChauffeur(session: SessionChauffeur): void {
  try {
    window.localStorage.setItem(CLE_SESSION, JSON.stringify(session));
  } catch {
    // Stockage indisponible (navigation privée, réglages navigateur) — la
    // session reste utilisable pour la requête en cours, juste pas
    // persistée. Pas une erreur fatale (doc artefacts : dégrader, pas casser).
  }
}

export function deconnecter(): void {
  try {
    window.localStorage.removeItem(CLE_SESSION);
  } catch {
    // idem ci-dessus
  }
}

export async function extraireErreurSupabase(reponse: Response): Promise<never> {
  const corps = (await reponse.json().catch(() => ({}))) as {
    error_description?: string;
    msg?: string;
    message?: string;
  };
  throw new ErreurAuthChauffeur(
    corps.error_description ??
      corps.msg ??
      corps.message ??
      `Échec de l'authentification (HTTP ${reponse.status}).`,
  );
}

/** Page qui reçoit les jetons Supabase (fragment `#access_token`), pour le
 * lien magique, la réinitialisation et la confirmation de changement
 * d'adresse. L'invitation chauffeur garde sa page dédiée. */
export function urlRetourAuth(): string {
  return `${window.location.origin}/auth/lien`;
}

export async function envoyerLienMagique(email: string): Promise<void> {
  const reponse = await fetch(
    `${SUPABASE_URL}/auth/v1/otp?redirect_to=${encodeURIComponent(urlRetourAuth())}`,
    {
      method: "POST",
      headers: enTetesSupabase(),
      body: JSON.stringify({ email, create_user: false }),
    },
  );
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
}

export async function demanderReinitialisation(email: string): Promise<void> {
  const reponse = await fetch(
    `${SUPABASE_URL}/auth/v1/recover?redirect_to=${encodeURIComponent(urlRetourAuth())}`,
    {
      method: "POST",
      headers: enTetesSupabase(),
      body: JSON.stringify({ email }),
    },
  );
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
}

export async function definirMotDePasseAvecJeton(
  accessToken: string,
  motDePasse: string,
): Promise<void> {
  const reponse = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    method: "PUT",
    headers: enTetesSupabase(accessToken),
    body: JSON.stringify({ password: motDePasse }),
  });
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
}

export async function changerEmailAvecJeton(accessToken: string, email: string): Promise<void> {
  const reponse = await fetch(
    `${SUPABASE_URL}/auth/v1/user?redirect_to=${encodeURIComponent(urlRetourAuth())}`,
    {
      method: "PUT",
      headers: enTetesSupabase(accessToken),
      body: JSON.stringify({ email }),
    },
  );
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
}

export async function connexionParMotDePasse(
  email: string,
  motDePasse: string,
): Promise<SessionChauffeur> {
  const reponse = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: enTetesSupabase(),
    body: JSON.stringify({ email, password: motDePasse }),
  });
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
  const corps = (await reponse.json()) as { access_token: string; refresh_token: string };
  const session: SessionChauffeur = {
    accessToken: corps.access_token,
    refreshToken: corps.refresh_token,
    dossierId: dossierIdDepuisJeton(corps.access_token),
    email,
  };
  enregistrerSessionChauffeur(session);
  return session;
}

/** Consomme le fragment d'URL du lien d'invitation Supabase
 * (`#access_token=...&refresh_token=...&type=invite`) — doc 19 §5.1-2. */
export async function accepterInvitation(fragmentUrl: string): Promise<SessionChauffeur> {
  const parametres = new URLSearchParams(fragmentUrl.replace(/^#/, ""));
  const accessToken = parametres.get("access_token");
  const refreshToken = parametres.get("refresh_token");
  if (!accessToken || !refreshToken) {
    throw new ErreurAuthChauffeur("Lien d'invitation invalide ou expiré.");
  }
  const reponse = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: enTetesSupabase(accessToken),
  });
  if (!reponse.ok) {
    await extraireErreurSupabase(reponse);
  }
  const utilisateur = (await reponse.json()) as { email: string };
  const session: SessionChauffeur = {
    accessToken,
    refreshToken,
    dossierId: dossierIdDepuisJeton(accessToken),
    email: utilisateur.email,
  };
  enregistrerSessionChauffeur(session);
  return session;
}

export async function definirMotDePasse(motDePasse: string): Promise<void> {
  const session = obtenirSession();
  if (!session) {
    throw new ErreurAuthChauffeur("Aucune session active.");
  }
  await definirMotDePasseAvecJeton(session.accessToken, motDePasse);
}

function baseUrlApi(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

const ESPACE_CHAUFFEUR = {
  lire: obtenirSession,
  enregistrer: enregistrerSessionChauffeur,
  effacer: deconnecter,
  pageConnexion: "/chauffeur/login",
};

/** Toute requête chauffeur vers l'API : jeton renouvelé au besoin, retour à
 * la connexion si la session ne peut plus l'être (`lib/session.ts`). */
function appelChauffeur(path: string, init: RequestInit = {}): Promise<Response> {
  return appelAuthentifie(ESPACE_CHAUFFEUR, `${baseUrlApi()}${path}`, init);
}

/** Requête brute avec le jeton chauffeur — factorisé pour `fetchAvecAuthChauffeur`
 * (JSON) et `telechargerAvecAuthChauffeur` (fichier binaire), doc 19 §8bis :
 * toutes les routes de niveau dossier exigent désormais ce jeton. */
async function requeteAvecAuthChauffeur(path: string): Promise<Response> {
  const reponse = await appelChauffeur(path);
  if (!reponse.ok) {
    throw erreurApi(await lireCorps(reponse), reponse);
  }
  return reponse;
}

/** Appel à `demo_api` avec le jeton chauffeur — pour toute route côté
 * chauffeur (doc 19 §4 : le serveur vérifie que le dossier appartient bien
 * à l'appelant, ceci ne fait qu'ajouter l'en-tête). */
export async function fetchAvecAuthChauffeur<T>(path: string): Promise<T> {
  const reponse = await requeteAvecAuthChauffeur(path);
  return (await reponse.json()) as T;
}

/** doc 19 §8bis (2026-09-11) : les exports de clôture/greffe-INPI sont des
 * liens `<a href>` qui ne peuvent pas porter d'en-tête `Authorization` — un
 * simple `<a>` échouerait en 401 maintenant que ces routes exigent un
 * jeton. On récupère donc le fichier ici (jeton dans l'en-tête, comme les
 * autres appels chauffeur), puis on déclenche l'enregistrement via une URL
 * d'objet temporaire, jamais en naviguant directement vers l'API. */
export async function telechargerAvecAuthChauffeur(
  path: string,
  nomFichier: string,
): Promise<void> {
  const reponse = await requeteAvecAuthChauffeur(path);
  const blob = await reponse.blob();
  const urlObjet = URL.createObjectURL(blob);
  try {
    const lien = document.createElement("a");
    lien.href = urlObjet;
    // Nom choisi par le serveur quand il en donne un (FEC : nom légal
    // `<SIREN>FEC<AAAAMMJJ>.txt`), sinon celui proposé par l'appelant.
    lien.download = nomDepuisContentDisposition(reponse) ?? nomFichier;
    lien.click();
  } finally {
    URL.revokeObjectURL(urlObjet);
  }
}

function nomDepuisContentDisposition(reponse: Response): string | null {
  const entete = reponse.headers.get("Content-Disposition");
  return entete?.match(/filename="([^"]+)"/)?.[1] ?? null;
}

/** doc 17 §9 Semaine 3 : le chauffeur tranche sa propre écriture (question
 * de catégorisation, doc 19 §5.6) — même endpoint que le gestionnaire
 * (`trancherTransaction`, lib/api.ts), avec le jeton en plus pour que le
 * serveur attribue la décision à la vraie identité (decide_par). */
/** « Tout confirmer » : tout ou rien côté API. */
export async function trancherEnGroupeChauffeur(
  dossierId: string,
  ecritureIds: string[],
  categorie: string,
): Promise<TransactionVue[]> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/decisions-groupees`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ categorie, ecriture_ids: ecritureIds }),
  });
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as TransactionVue[];
}

export async function trancherTransactionChauffeur(
  dossierId: string,
  ecritureId: string,
  categorie: string,
): Promise<TransactionVue> {
  const reponse = await appelChauffeur(
    `/dossiers/${dossierId}/transactions/${ecritureId}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ categorie }),
    },
  );
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as TransactionVue;
}

/** doc 19 §5.3, doc 20 §4bis : signature (démo, jamais qualifiée RGS) du
 * dossier de dépôt greffe/INPI — authentifiée pour que `demo_api.py`
 * attribue vraiment `signataire` à l'indiv connecté (`identite.user_id`),
 * pas au stub `UTILISATEUR_DEMO`. Déplacé depuis lib/api.ts le
 * 2026-09-11 : cet écran quitte le gestionnaire (doc 19 §2.1/§2.4), donc
 * la version anonyme n'a plus de raison d'être appelée. */
export async function signerGreffeInpiChauffeur(dossierId: string): Promise<SignatureGreffeVue> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/greffe-inpi/signature`, {
    method: "POST",
  });
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as SignatureGreffeVue;
}

/** doc 17 §9 Semaine 3, doc 19 §5.7 : photo de justificatif jointe par le
 * chauffeur — upload multipart, jamais lue côté serveur (pas d'OCR). */
export async function joindreJustificatifChauffeur(
  dossierId: string,
  ecritureId: string,
  fichier: File,
): Promise<TransactionVue> {
  const corpsFormulaire = new FormData();
  corpsFormulaire.append("fichier", fichier);
  const reponse = await appelChauffeur(
    `/dossiers/${dossierId}/transactions/${ecritureId}/justificatif`,
    {
      method: "POST",
        body: corpsFormulaire,
    },
  );
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as TransactionVue;
}

/** Notifications internes du chauffeur, les plus récentes d'abord. */
export async function listerNotificationsChauffeur(dossierId: string): Promise<NotificationVue[]> {
  return fetchAvecAuthChauffeur<NotificationVue[]>(`/dossiers/${dossierId}/notifications`);
}

/** Ouvrir la cloche vaut lecture : tout ce qui n'était pas lu le devient. */
export async function marquerNotificationsLuesChauffeur(dossierId: string): Promise<void> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/notifications/lues`, {
    method: "POST",
  });
  if (!reponse.ok) {
    throw new ApiError(`HTTP ${reponse.status}`, reponse.status);
  }
}

export async function lireProvisionsCloture(dossierId: string): Promise<ProvisionClotureVue[]> {
  const vue = await fetchAvecAuthChauffeur<{ lignes: ProvisionClotureVue[] }>(
    `/dossiers/${dossierId}/provisions-cloture`,
  );
  return vue.lignes;
}

export async function enregistrerProvisionsCloture(
  dossierId: string,
  lignes: ProvisionClotureVue[],
): Promise<ProvisionClotureVue[]> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/provisions-cloture`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lignes }),
  });
  if (!reponse.ok) {
    throw erreurApi(await lireCorps(reponse), reponse);
  }
  const vue = (await reponse.json()) as { lignes: ProvisionClotureVue[] };
  return vue.lignes;
}

/** La validation de clôture : le texte d'attestation présenté, renvoyé tel
 * quel, prouve ce que le chauffeur a accepté. */
export async function validerClotureChauffeur(
  dossierId: string,
  attestation: string,
): Promise<ClotureExerciceVue> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/cloture-exercice`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ attestation }),
  });
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as ClotureExerciceVue;
}

/** La décision d'affectation : un scénario proposé ou « libre » avec son
 * propre montant de dividendes, en centimes. */
export async function deciderAffectationChauffeur(
  dossierId: string,
  scenario: string,
  dividendesCts: number,
): Promise<AffectationVue> {
  const reponse = await appelChauffeur(`/dossiers/${dossierId}/affectation`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ scenario, dividendes_cts: dividendesCts }),
  });
  const corps = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(corps, reponse);
  }
  return corps as AffectationVue;
}

/** POST JSON authentifié : factorise les envois du chauffeur qui renvoient
 * une vue, avec le message d'erreur de l'API. */
async function envoyerChauffeur<T>(path: string, corps: unknown): Promise<T> {
  const reponse = await appelChauffeur(`${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(corps),
  });
  const donnees = await lireCorps(reponse);
  if (!reponse.ok) {
    throw erreurApi(donnees, reponse);
  }
  return donnees as T;
}

export function declarerDividendesChauffeur(
  dossierId: string,
  verseLe: string,
  dispensePrelevement: boolean,
): Promise<DividendesVue> {
  return envoyerChauffeur(`/dossiers/${dossierId}/dividendes`, {
    verse_le: verseLe,
    dispense_prelevement: dispensePrelevement,
  });
}

export function saisirBulletinChauffeur(
  dossierId: string,
  bulletin: {
    mois: string;
    brut_cts: number;
    cotisations_salariales_cts: number;
    cotisations_patronales_cts: number;
    prelevement_a_la_source_cts: number;
  },
): Promise<BulletinVue> {
  return envoyerChauffeur(`/dossiers/${dossierId}/bulletins`, bulletin);
}
