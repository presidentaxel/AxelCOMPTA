/** Connexion et session gestionnaire (doc 03 §7, doc 19 §2.1).
 *
 * Même mécanisme que le chauffeur (`auth-chauffeur.ts`, Supabase Auth en
 * REST direct) : ce qui change, c'est le lien porté par le compte. Ici
 * `app_metadata.tenant_id` (posé côté serveur, jamais modifiable par
 * l'utilisateur), là `app_metadata.dossier_id` (même emplacement). Le décodage du jeton plus
 * bas ne sert qu'à refuser tôt un compte sans lien gestionnaire ; la
 * vérification réelle est côté serveur (`demo_auth.verifier_jwt`) à chaque
 * appel.
 *
 * Session en `localStorage`, clé distincte de celle du chauffeur : un même
 * navigateur peut avoir les deux sessions sans qu'elles s'écrasent.
 */

import { ApiError } from "./api";
import { appelAuthentifie } from "./session";
import {
  changerEmailAvecJeton,
  decoderChargeUtileJwt,
  definirMotDePasseAvecJeton,
  enTetesSupabase,
  ErreurAuthChauffeur,
  extraireErreurSupabase,
  URL_SUPABASE,
} from "./auth-chauffeur";
import type { AlerteAnomalie, DossierAgregat } from "./types";

const CLE_SESSION = "axelcompta_session_gestionnaire";

export type SessionGestionnaire = {
  accessToken: string;
  refreshToken: string;
  tenantId: string;
  email: string;
};

export class ErreurAuthGestionnaire extends Error {}

function baseUrlApi(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function tenantIdDepuisJeton(accessToken: string): string {
  const charge = decoderChargeUtileJwt(accessToken);
  const metadata = charge.app_metadata as { tenant_id?: string } | undefined;
  const tenantId = metadata?.tenant_id;
  if (!tenantId) {
    throw new ErreurAuthGestionnaire("Ce compte n'est lié à aucun portefeuille.");
  }
  return tenantId;
}

export function obtenirSessionGestionnaire(): SessionGestionnaire | null {
  try {
    const brut = window.localStorage.getItem(CLE_SESSION);
    return brut ? (JSON.parse(brut) as SessionGestionnaire) : null;
  } catch {
    return null;
  }
}

export function ouvrirSessionGestionnaire(
  accessToken: string,
  refreshToken: string,
  email: string,
): SessionGestionnaire {
  const session: SessionGestionnaire = {
    accessToken,
    refreshToken,
    tenantId: tenantIdDepuisJeton(accessToken),
    email,
  };
  try {
    window.localStorage.setItem(CLE_SESSION, JSON.stringify(session));
  } catch {
    // Session utilisable pour cette page, simplement pas persistée.
  }
  return session;
}

export function deconnecterGestionnaire(): void {
  try {
    window.localStorage.removeItem(CLE_SESSION);
  } catch {
    // Stockage indisponible : rien à effacer, pas une erreur.
  }
}

export async function connexionGestionnaire(
  email: string,
  motDePasse: string,
): Promise<SessionGestionnaire> {
  const reponse = await fetch(`${URL_SUPABASE}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: enTetesSupabase(),
    body: JSON.stringify({ email, password: motDePasse }),
  });
  if (!reponse.ok) {
    try {
      await extraireErreurSupabase(reponse);
    } catch (exception) {
      // Même erreur Supabase, réémise sous le type gestionnaire.
      throw new ErreurAuthGestionnaire(
        exception instanceof ErreurAuthChauffeur ? exception.message : "Échec de la connexion.",
      );
    }
  }
  const corps = (await reponse.json()) as { access_token: string; refresh_token: string };
  return ouvrirSessionGestionnaire(corps.access_token, corps.refresh_token, email);
}

export async function changerMotDePasseGestionnaire(motDePasse: string): Promise<void> {
  const session = obtenirSessionGestionnaire();
  if (!session) {
    throw new ErreurAuthGestionnaire("Aucune session active.");
  }
  try {
    await definirMotDePasseAvecJeton(session.accessToken, motDePasse);
  } catch (exception) {
    throw new ErreurAuthGestionnaire(
      exception instanceof ErreurAuthChauffeur ? exception.message : "Échec du changement.",
    );
  }
}

export async function changerEmailGestionnaire(email: string): Promise<void> {
  const session = obtenirSessionGestionnaire();
  if (!session) {
    throw new ErreurAuthGestionnaire("Aucune session active.");
  }
  try {
    await changerEmailAvecJeton(session.accessToken, email);
  } catch (exception) {
    throw new ErreurAuthGestionnaire(
      exception instanceof ErreurAuthChauffeur ? exception.message : "Échec du changement.",
    );
  }
}

/** Requête authentifiée vers `demo_api` (`lib/session.ts`) : jeton renouvelé
 * au besoin, retour à la connexion si la session ne peut plus l'être. Un
 * 403 est un refus de rôle (membre, lecture) : la session reste, l'appelant
 * reçoit la réponse et affiche le refus. */
async function requeteGestionnaire(path: string, init: RequestInit = {}): Promise<Response> {
  return appelAuthentifie(ESPACE_GESTIONNAIRE, `${baseUrlApi()}${path}`, init);
}

function enregistrerSessionGestionnaire(session: SessionGestionnaire): void {
  try {
    window.localStorage.setItem(CLE_SESSION, JSON.stringify(session));
  } catch {
    // Session utilisable pour cette page, simplement pas persistée.
  }
}

const ESPACE_GESTIONNAIRE = {
  lire: obtenirSessionGestionnaire,
  enregistrer: enregistrerSessionGestionnaire,
  effacer: deconnecterGestionnaire,
  pageConnexion: "/connexion",
};

const CLE_PORTEFEUILLE = "axelcompta_portefeuille";

/** Dernière liste affichée, pour ne pas attendre le recalcul à chaque navigation. */
export function lirePortefeuilleSession(): DossierAgregat[] | null {
  try {
    const brut = window.sessionStorage.getItem(CLE_PORTEFEUILLE);
    if (!brut) return null;
    const valeur = JSON.parse(brut) as DossierAgregat[];
    return Array.isArray(valeur) ? valeur : null;
  } catch {
    return null;
  }
}

export type ParametresDemo = {
  digifactory_branche: boolean;
};

/** Faux Digifactory. Branché, l'app chauffeur n'a pas « Connecter ma banque ». */
export async function lireParametresDemo(): Promise<ParametresDemo> {
  const reponse = await requeteGestionnaire("/demo/parametres");
  if (!reponse.ok) {
    throw new ApiError(`API démo (/demo/parametres) : HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as ParametresDemo;
}

export async function reglerDigifactoryDemo(branche: boolean): Promise<ParametresDemo> {
  const reponse = await requeteGestionnaire("/demo/parametres", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ digifactory_branche: branche }),
  });
  if (!reponse.ok) {
    throw new ApiError(`API démo (/demo/parametres) : HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as ParametresDemo;
}

/** doc 19 §2.1 : la liste agrégée, tout ce que voit le gestionnaire. */
export async function listerDossiers(): Promise<DossierAgregat[]> {
  const reponse = await requeteGestionnaire("/dossiers");
  if (!reponse.ok) {
    throw new ApiError(`API démo (/dossiers) : HTTP ${reponse.status}`, reponse.status);
  }
  const dossiers = (await reponse.json()) as DossierAgregat[];
  try {
    window.sessionStorage.setItem(CLE_PORTEFEUILLE, JSON.stringify(dossiers));
  } catch {
    // Affichage quand même, simplement pas mémorisé pour la prochaine page.
  }
  return dossiers;
}

export async function listerAnomalies(dossierId: string): Promise<AlerteAnomalie[]> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/anomalies`);
  if (reponse.status === 401 || reponse.status === 403) {
    throw new ErreurAuthGestionnaire();
  }
  if (!reponse.ok) {
    throw new ApiError(`API démo (/anomalies) : HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as AlerteAnomalie[];
}

export async function instruireAlerte(
  dossierId: string,
  alerteId: string,
  decision: AlerteAnomalie["etat"],
  commentaire: string,
): Promise<AlerteAnomalie> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/anomalies/${encodeURIComponent(alerteId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, commentaire }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? "La qualification a échoué.", reponse.status);
  }
  return (await reponse.json()) as AlerteAnomalie;
}

export type RoleMembre = "admin" | "membre" | "lecture";

export type StatutMembre = "invité" | "actif";

export type MembrePortefeuille = { email: string; role: RoleMembre; statut: StatutMembre };

const CLE_EQUIPE = "axelcompta_equipe";
const ROLES_MEMBRE: readonly RoleMembre[] = ["admin", "membre", "lecture"];
const STATUTS_MEMBRE: readonly StatutMembre[] = ["invité", "actif"];

function estMembre(valeur: unknown): valeur is MembrePortefeuille {
  if (!valeur || typeof valeur !== "object") return false;
  const membre = valeur as MembrePortefeuille;
  return (
    typeof membre.email === "string" &&
    ROLES_MEMBRE.includes(membre.role) &&
    STATUTS_MEMBRE.includes(membre.statut)
  );
}

/** Dernière équipe affichée, pour ne pas attendre Supabase à chaque navigation. */
export function lireEquipeSession(): MembrePortefeuille[] | null {
  try {
    const brut = window.sessionStorage.getItem(CLE_EQUIPE);
    if (!brut) return null;
    const valeur = JSON.parse(brut) as unknown;
    if (!Array.isArray(valeur) || !valeur.every(estMembre)) return null;
    return valeur;
  } catch {
    return null;
  }
}

function memoriserEquipe(membres: MembrePortefeuille[]): void {
  try {
    window.sessionStorage.setItem(CLE_EQUIPE, JSON.stringify(membres));
  } catch {
    // Affichage quand même, simplement pas mémorisé pour la prochaine page.
  }
}

/** Ajoute ou remplace un membre dans la liste mémorisée, sans relire Supabase. */
export function integrerMembreSession(
  actuels: MembrePortefeuille[],
  membre: MembrePortefeuille,
): MembrePortefeuille[] {
  const suite = [
    ...actuels.filter((item) => item.email.toLowerCase() !== membre.email.toLowerCase()),
    membre,
  ].sort((a, b) => a.email.localeCompare(b.email, "fr"));
  memoriserEquipe(suite);
  return suite;
}

export async function listerMembres(): Promise<MembrePortefeuille[]> {
  const reponse = await requeteGestionnaire("/portefeuille/membres");
  if (!reponse.ok) {
    throw new ApiError(`API (/portefeuille/membres) : HTTP ${reponse.status}`, reponse.status);
  }
  const membres = (await reponse.json()) as MembrePortefeuille[];
  return membres;
}

/** Mémorise une liste acceptée. Un chargement déjà dépassé ne doit pas écrire. */
export function publierEquipeSession(membres: MembrePortefeuille[]): void {
  memoriserEquipe(membres);
}

export async function inviterMembre(email: string, role: RoleMembre): Promise<MembrePortefeuille> {
  const reponse = await requeteGestionnaire("/portefeuille/membres", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => ({}));
    throw new ApiError(corps.detail ?? `HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as MembrePortefeuille;
}

export async function lireNomPortefeuille(): Promise<string> {
  const reponse = await requeteGestionnaire("/portefeuille");
  if (!reponse.ok) return "";
  const corps = (await reponse.json()) as { nom: string };
  return corps.nom;
}

export async function renommerPortefeuille(nom: string): Promise<string> {
  const reponse = await requeteGestionnaire("/portefeuille", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nom }),
  });
  if (!reponse.ok) {
    throw new ApiError("Impossible d'enregistrer le nom.", reponse.status);
  }
  const corps = (await reponse.json()) as { nom: string };
  return corps.nom;
}

export async function retirerDossier(dossierId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/retirer`, { method: "POST" });
  if (!reponse.ok) {
    throw new ApiError("Impossible de retirer ce dossier.", reponse.status);
  }
}

export type RegleRappel = {
  id: string;
  libelle: string;
  message: string;
  canaux: string[];
  portee: string;
  dossier_ids: string[];
  declencheur: string;
  jours_avant: number | null;
};

export async function listerRegles(): Promise<RegleRappel[]> {
  const reponse = await requeteGestionnaire("/regles-rappel");
  if (!reponse.ok) {
    throw new ApiError("Impossible de charger les rappels.", reponse.status);
  }
  return (await reponse.json()) as RegleRappel[];
}

export async function creerRegle(regle: {
  libelle: string;
  message: string;
  canaux: string[];
  portee?: string;
  dossier_ids?: string[];
  declencheur?: string;
  jours_avant?: number | null;
}): Promise<void> {
  const reponse = await requeteGestionnaire("/regles-rappel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(regle),
  });
  if (!reponse.ok) {
    throw new ApiError("Impossible d'enregistrer la règle.", reponse.status);
  }
}

export async function declencherRappel(regleId: string, dossierId: string): Promise<void> {
  const reponse = await requeteGestionnaire("/rappels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ regle_id: regleId, dossier_id: dossierId }),
  });
  if (!reponse.ok) {
    throw new ApiError("Impossible d'envoyer le rappel.", reponse.status);
  }
}

export async function changerRole(email: string, role: RoleMembre): Promise<MembrePortefeuille> {
  const reponse = await requeteGestionnaire("/portefeuille/membres", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
  if (!reponse.ok) {
    throw new ApiError("Impossible de changer le rôle.", reponse.status);
  }
  return (await reponse.json()) as MembrePortefeuille;
}

export async function inviterChauffeur(
  dossierId: string,
  email: string,
): Promise<{ dossier_id: string; email: string; statut: string }> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/inviter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const corps = await reponse.json();
  if (!reponse.ok) {
    throw new ApiError(corps.detail ?? `HTTP ${reponse.status}`, reponse.status);
  }
  return corps;
}

export type ResultatInvitation =
  | "invité"
  | "deja_invite"
  | "dossier_inconnu"
  | "email_invalide"
  | "doublon_dans_le_lot"
  | "erreur";

export type InvitationsMasse = {
  lignes: { dossier_id: string; email: string; resultat: ResultatInvitation }[];
  nb_invitees: number;
};

/** doc 19 §3.1 : invitation en masse depuis une base clients (500 lignes au
 * plus par envoi, résultat ligne par ligne). */
export async function inviterEnMasse(
  lignes: { dossier_id: string; email: string }[],
): Promise<InvitationsMasse> {
  const reponse = await requeteGestionnaire("/invitations/en-masse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invitations: lignes }),
  });
  const corps = await reponse.json();
  if (!reponse.ok) {
    throw new ApiError(
      typeof corps.detail === "string" ? corps.detail : `HTTP ${reponse.status}`,
      reponse.status,
    );
  }
  return corps as InvitationsMasse;
}

export type PartieDemo = { cle: string; libelle: string; detail: string };

/** Menu Démo : le portefeuille de démo seulement (`TENANT_DEMO`). */
export function estPortefeuilleDemo(): boolean {
  return obtenirSessionGestionnaire()?.tenantId === "TENANT_DEMO";
}

export async function listerPartiesDemo(): Promise<PartieDemo[]> {
  const reponse = await requeteGestionnaire("/demo/parties");
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => ({}));
    throw new ApiError(corps.detail ?? `HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as PartieDemo[];
}

/** Remet à neuf les parties cochées. Le grand livre n'en fait jamais partie. */
export async function reinitialiserDemo(parties: string[]): Promise<string[]> {
  const reponse = await requeteGestionnaire("/demo/reinitialiser", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parties }),
  });
  const corps = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    throw new ApiError(corps.detail ?? `HTTP ${reponse.status}`, reponse.status);
  }
  window.sessionStorage.removeItem(CLE_PORTEFEUILLE);
  return corps.dossiers as string[];
}

export type ModeRelance = "auto" | "manuel";

export type ConnexionDossier = {
  dossier_id: string;
  nom: string;
  statut: "actif" | "a_renouveler" | "expire" | "jamais_connecte";
  sante: "ok" | "en_pause" | "sans_acces" | "auth_requise" | "jamais_connecte";
  expire_le: string | null;
  jours_restants: number | null;
  dernier_rafraichissement: string | null;
  relance: ModeRelance;
  relance_propre: boolean;
};

export type ConnexionsBancaires = {
  relance_portefeuille: ModeRelance;
  compteurs: Record<"actif" | "a_renouveler" | "expire" | "jamais_connecte", number>;
  a_reconnecter: number;
  dossiers: ConnexionDossier[];
};

/** doc 14 §2.2 : l'état des connexions bancaires du portefeuille. */
export async function lireConnexionsBancaires(): Promise<ConnexionsBancaires> {
  const reponse = await requeteGestionnaire("/portefeuille/connexions-bancaires");
  if (!reponse.ok) {
    throw new ApiError("Impossible de charger les connexions bancaires.", reponse.status);
  }
  return (await reponse.json()) as ConnexionsBancaires;
}

export async function reglerRelancePortefeuille(mode: ModeRelance): Promise<void> {
  const reponse = await requeteGestionnaire("/portefeuille/relance-consentement", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(corps.detail ?? "Réglage refusé.", reponse.status);
  }
}

/** `null` : le dossier suit le mode du portefeuille. */
export async function reglerRelanceDossier(dossierId: string, mode: ModeRelance | null): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/relance-consentement`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(corps.detail ?? "Réglage refusé.", reponse.status);
  }
}
