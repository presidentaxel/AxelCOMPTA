/** Connexion et session gestionnaire (doc 03 §7, doc 19 §2.1).
 *
 * Même mécanisme que le chauffeur (`auth-chauffeur.ts`, Supabase Auth en
 * REST direct) : ce qui change, c'est le lien porté par le compte. Ici
 * `app_metadata.tenant_id` (posé côté serveur, jamais modifiable par
 * l'utilisateur), là `app_metadata.dossier_id` (même emplacement). Le décodage du jeton plus
 * bas ne sert qu'à refuser tôt un compte sans lien gestionnaire ; la
 * vérification réelle est côté serveur (`api/auth.py`, `verifier_jwt`) à chaque
 * appel.
 *
 * Session en `localStorage`, clé distincte de celle du chauffeur : un même
 * navigateur peut avoir les deux sessions sans qu'elles s'écrasent.
 */

import { ApiError } from "./api";
import { coteOuverte } from "./cote-connexion";
import {
  MESSAGE_ESPACE_CHAUFFEUR,
  MESSAGE_SANS_PORTEFEUILLE,
  MESSAGE_SESSION,
} from "./messages-auth";
import { appelAuthentifie, erreurApi, lireCorps } from "./session";
import {
  changerEmailAvecJeton,
  decoderChargeUtileJwt,
  definirMotDePasseAvecJeton,
  enTetesSupabase,
  ErreurAuthChauffeur,
  extraireErreurSupabase,
  URL_SUPABASE,
} from "./auth-chauffeur";
import type {
  AlerteAnomalie,
  EtatCategorisation,
  DossierAgregat,
  EntreeQuarantaine,
  EvenementAnomalie,
  FileExpert,
  ImputationFaite,
  NouveauChauffeur,
  OperationsClassees,
  ReglageTags,
  Synchronisation,
} from "./types";

import type { FicheAnnuaireRollee, FicheRollee, PassageRollee, RolleePortefeuille } from "./liens-rollee";
import type { AnalyseFec, OuvertureVue } from "./ouverture";
const CLE_SESSION = "axelcompta_session_gestionnaire";

export type SessionGestionnaire = {
  accessToken: string;
  refreshToken: string;
  tenantId: string;
  email: string;
};

export class ErreurAuthGestionnaire extends Error {
  override name = "ErreurAuthGestionnaire";
}

function baseUrlApi(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function tenantIdDepuisJeton(accessToken: string): string {
  const charge = decoderChargeUtileJwt(accessToken);
  const metadata = charge.app_metadata as { tenant_id?: string } | undefined;
  const tenantId = metadata?.tenant_id;
  if (!tenantId) {
    throw new ErreurAuthGestionnaire(MESSAGE_SANS_PORTEFEUILLE);
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
  const charge = decoderChargeUtileJwt(accessToken);
  const cote = coteOuverte(charge.app_metadata, "gestionnaire");
  if (cote !== "gestionnaire") {
    throw new ErreurAuthGestionnaire(
      cote === "interdit" ? MESSAGE_ESPACE_CHAUFFEUR : MESSAGE_SANS_PORTEFEUILLE,
    );
  }
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
    throw new ErreurAuthGestionnaire(MESSAGE_SESSION);
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
    throw new ErreurAuthGestionnaire(MESSAGE_SESSION);
  }
  try {
    await changerEmailAvecJeton(session.accessToken, email);
  } catch (exception) {
    throw new ErreurAuthGestionnaire(
      exception instanceof ErreurAuthChauffeur ? exception.message : "Échec du changement.",
    );
  }
}

/** Requête authentifiée vers l'API (`lib/session.ts`) : jeton renouvelé
 * au besoin, retour à la connexion si la session ne peut plus l'être. Un
 * 403 est un refus de rôle (membre, lecture) : la session reste, l'appelant
 * reçoit la réponse et affiche le refus. */
async function requeteGestionnaire(path: string, init: RequestInit = {}): Promise<Response> {
  const entetes = new Headers(init.headers);
  entetes.set("X-Cote", "gestionnaire");
  return appelAuthentifie(ESPACE_GESTIONNAIRE, `${baseUrlApi()}${path}`, {
    ...init,
    headers: entetes,
  });
}

function enregistrerSessionGestionnaire(session: SessionGestionnaire): void {
  try {
    window.localStorage.setItem(CLE_SESSION, JSON.stringify(session));
  } catch {
    // Session utilisable pour cette page, simplement pas persistée.
  }
}

/** AXE-812 : ce que l'écran doit savoir de la session (rôle, code exigé). */
export type Moi = { email: string; role: string; mfa_requise: boolean; aal: string };

export async function lireMoi(): Promise<Moi> {
  const reponse = await requeteGestionnaire("/portefeuille/moi");
  if (!reponse.ok) {
    throw erreurApi(await lireCorps(reponse), reponse);
  }
  return (await reponse.json()) as Moi;
}

/** AXE-812 : trace la connexion au journal du portefeuille. Une trace
 * manquée ne bloque pas l'entrée. */
export async function tracerConnexionGestionnaire(): Promise<void> {
  try {
    await requeteGestionnaire("/session/connexion", { method: "POST" });
  } catch {
    // Le serveur répondra à la prochaine requête ; l'entrée n'en dépend pas.
  }
}

/** AXE-812 : les jetons `aal2` obtenus après la vérification du code. */
export function remplacerJetonsGestionnaire(accessToken: string, refreshToken: string): void {
  const session = obtenirSessionGestionnaire();
  if (!session) return;
  enregistrerSessionGestionnaire({ ...session, accessToken, refreshToken });
}

/** AXE-812 : un autre admin retire les facteurs d'un membre. */
export async function reinitialiserMfaMembre(email: string): Promise<number> {
  const reponse = await requeteGestionnaire(
    `/portefeuille/membres/${encodeURIComponent(email)}/mfa/reinitialiser`,
    { method: "POST" },
  );
  if (!reponse.ok) {
    throw erreurApi(await lireCorps(reponse), reponse);
  }
  return ((await reponse.json()) as { facteurs_retires: number }).facteurs_retires;
}

export type HabilitationExpert = {
  email: string;
  nom: string;
  cabinet: string;
  numero_ordre: string;
  lettre_mission: string;
  date_lettre: string;
  dossiers: string[];
};

export type EngagementExpert = {
  version: string;
  texte: string;
  accepte: boolean;
  habilitation: HabilitationExpert | null;
};

/** AXE-800 : le texte d'engagement en vigueur, et s'il est déjà accepté. */
export async function lireEngagementExpert(): Promise<EngagementExpert> {
  const reponse = await requeteGestionnaire("/expert/engagement");
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as EngagementExpert;
}

/** AXE-800 : l'expert accepte le texte affiché, mot pour mot. */
export async function accepterEngagementExpert(version: string, texte: string): Promise<void> {
  const reponse = await requeteGestionnaire("/expert/engagement", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version, texte }),
  });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
}

/** AXE-800 : un admin déclare l'expert-comptable du portefeuille. */
export async function habiliterExpert(entree: HabilitationExpert): Promise<HabilitationExpert> {
  const reponse = await requeteGestionnaire("/portefeuille/experts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entree),
  });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as HabilitationExpert;
}

/** AXE-808 : canal branché → date du réglage. Jamais un identifiant. */
export async function lireIntegrationsEnvoi(): Promise<Record<string, string>> {
  const reponse = await requeteGestionnaire("/portefeuille/integrations/envoi");
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return ((await reponse.json()) as { canaux: Record<string, string> }).canaux;
}

/** AXE-872 : une intégration nommée du portefeuille. Jamais d'identifiant. */
export type Branchement = {
  id: string;
  type: "mail" | "sms" | "digifactory" | "rollee";
  fournisseur: string;
  nom: string;
  par_defaut: boolean;
  actif: boolean;
  maj_le: string | null;
  /** Champs non secrets (serveur, expéditeur…). Jamais un jeton. */
  champs: Record<string, string>;
  /** Noms des secrets déjà chiffrés. La valeur ne revient pas. */
  secrets: string[];
};

export type EssaiBranchement = {
  statut: "ok" | "echec" | "indisponible";
  message: string;
};

export async function listerBranchements(): Promise<Branchement[]> {
  const reponse = await requeteGestionnaire("/portefeuille/integrations");
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as Branchement[];
}

export async function ajouterBranchement(
  type: Branchement["type"],
  fournisseur: string,
  nom: string,
  parametres: Record<string, string>,
): Promise<Branchement[]> {
  const reponse = await requeteGestionnaire("/portefeuille/integrations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, fournisseur, nom, parametres }),
  });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as Branchement[];
}

/** Champs absents : inchangés. `parametres` remplace tous les identifiants. */
export async function modifierBranchement(
  id: string,
  modification: {
    nom?: string;
    parametres?: Record<string, string>;
    par_defaut?: boolean;
    actif?: boolean;
  },
): Promise<Branchement[]> {
  const reponse = await requeteGestionnaire(
    `/portefeuille/integrations/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(modification),
    },
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as Branchement[];
}

export type FicheWebhook = {
  url: string;
  secret: string;
  methode: string;
  evenements: string[];
  joignable: boolean;
};

export async function preparerWebhook(id: string): Promise<FicheWebhook> {
  const reponse = await requeteGestionnaire(
    `/portefeuille/integrations/${encodeURIComponent(id)}/webhook`,
    { method: "POST" },
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as FicheWebhook;
}

export async function testerBranchement(id: string): Promise<EssaiBranchement> {
  const reponse = await requeteGestionnaire(
    `/portefeuille/integrations/${encodeURIComponent(id)}/tester`,
    { method: "POST" },
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as EssaiBranchement;
}

/** Type → branchement choisi pour ce dossier (absent : celui par défaut). */
export async function lireBranchementsDossier(
  dossierId: string,
): Promise<Record<string, string>> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${encodeURIComponent(dossierId)}/integrations`,
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return ((await reponse.json()) as { choix: Record<string, string> }).choix;
}

export async function choisirBranchementDossier(
  dossierId: string,
  type: Branchement["type"],
  branchementId: string | null,
): Promise<Record<string, string>> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${encodeURIComponent(dossierId)}/integrations/${type}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ branchement_id: branchementId }),
    },
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return ((await reponse.json()) as { choix: Record<string, string> }).choix;
}

/** AXE-819 : plateformes reliées par le chauffeur, en nombres (doc 19). */
export type SynthesePlateformes = {
  reliees: number;
  attendues: number;
  a_reconnecter: number;
  manquantes: string[];
};

export async function lireSynthesePlateformes(dossierId: string): Promise<SynthesePlateformes> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${encodeURIComponent(dossierId)}/plateformes/synthese`,
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as SynthesePlateformes;
}

export type EnvoiRappel = {
  canal: string;
  branchement?: string | null;
  statut: "en_attente" | "envoye" | "echec" | "ignore";
  tentatives: number;
  raison: string | null;
  le: string | null;
};

/** AXE-808 : suivi des rappels envoyés à une entreprise. */
export async function lireEnvois(dossierId: string): Promise<EnvoiRappel[]> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/envois`);
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as EnvoiRappel[];
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

/** AXE-800 : le mode expert est à l'expert-comptable habilité, engagement
 * accepté. Un autre rôle reçoit 403 avec la raison : ce n'est pas une
 * session expirée, l'écran l'explique (et propose l'engagement). */
export class ModeExpertRefuse extends Error {
  override name = "ModeExpertRefuse";
}

async function refusExpert(reponse: Response): Promise<never> {
  const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
  throw new ModeExpertRefuse(corps.detail ?? "Réservé à l'expert-comptable du portefeuille.");
}

export async function lireFileExpert(): Promise<FileExpert> {
  const reponse = await requeteGestionnaire("/expert/file");
  if (reponse.status === 401) {
    throw new ErreurAuthGestionnaire();
  }
  if (reponse.status === 403) {
    await refusExpert(reponse);
  }
  if (!reponse.ok) {
    throw new ApiError(`API démo (/expert/file) : HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as FileExpert;
}

/** Impute l'écriture et retourne les sujets à jour de ce dossier seul. */
export async function imputerExpert(
  dossierId: string,
  ecritureId: string,
  compte: string,
  motif: string,
): Promise<ImputationFaite> {
  const reponse = await requeteGestionnaire("/expert/imputations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dossier_id: dossierId, ecriture_id: ecritureId, compte, motif }),
  });
  if (reponse.status === 401) {
    throw new ErreurAuthGestionnaire("Session expirée.");
  }
  if (reponse.status === 403) {
    await refusExpert(reponse);
  }
  if (!reponse.ok) {
    let detail = `HTTP ${reponse.status}`;
    try {
      const corps = (await reponse.json()) as { detail?: string };
      if (corps.detail) detail = corps.detail;
    } catch {
      // Le message HTTP suffit.
    }
    throw new ApiError(detail, reponse.status);
  }
  return (await reponse.json()) as ImputationFaite;
}

export async function annulerImputation(
  dossierId: string,
  ecritureId: string,
  contrepassationId: string,
  motif: string,
): Promise<void> {
  const reponse = await requeteGestionnaire("/expert/imputations/annuler", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dossier_id: dossierId,
      ecriture_id: ecritureId,
      contrepassation_id: contrepassationId,
      motif,
    }),
  });
  if (reponse.status === 401) {
    throw new ErreurAuthGestionnaire("Session expirée.");
  }
  if (reponse.status === 403) {
    await refusExpert(reponse);
  }
  if (!reponse.ok) {
    let detail = "Impossible d'annuler l'imputation.";
    try {
      const corps = (await reponse.json()) as { detail?: string };
      if (corps.detail) detail = corps.detail;
    } catch {
      // Le message par défaut suffit.
    }
    throw new ApiError(detail, reponse.status);
  }
}

export async function listerAnomalies(dossierId: string): Promise<AlerteAnomalie[]> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/anomalies`);
  if (reponse.status === 401) {
    throw new ErreurAuthGestionnaire();
  }
  if (reponse.status === 403) {
    await refusExpert(reponse);
  }
  if (!reponse.ok) {
    throw new ApiError(`API démo (/anomalies) : HTTP ${reponse.status}`, reponse.status);
  }
  return (await reponse.json()) as AlerteAnomalie[];
}

export async function lireHistoriqueAlerte(
  dossierId: string,
  alerteId: string,
): Promise<EvenementAnomalie[]> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${dossierId}/anomalies/${encodeURIComponent(alerteId)}/historique`,
  );
  if (!reponse.ok) {
    throw new ApiError("Impossible de lire l'historique.", reponse.status);
  }
  return (await reponse.json()) as EvenementAnomalie[];
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

export type RoleMembre = "admin" | "membre" | "lecture" | "expert_comptable";

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

/** AXE-825 : le modèle de catégorisation est-il chargé côté serveur ?
 * `null` si l'état n'a pas pu être lu (on n'affiche alors rien). */
export async function lireCategorisation(): Promise<EtatCategorisation | null> {
  const reponse = await requeteGestionnaire("/portefeuille/categorisation");
  if (!reponse.ok) return null;
  return (await reponse.json()) as EtatCategorisation;
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

export async function listerDossiersRetires(): Promise<{ dossier_id: string; nom: string }[]> {
  const reponse = await requeteGestionnaire("/portefeuille/retires");
  if (!reponse.ok) return [];
  return (await reponse.json()) as { dossier_id: string; nom: string }[];
}

export async function restaurerDossier(dossierId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/restaurer`, { method: "POST" });
  if (!reponse.ok) {
    throw new ApiError("Impossible de remettre ce dossier dans la liste.", reponse.status);
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
  actif: boolean;
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
    let detail = "Impossible d'enregistrer la règle.";
    try {
      const corps = (await reponse.json()) as { detail?: string };
      if (corps.detail) detail = corps.detail;
    } catch {
      // Le message par défaut suffit.
    }
    throw new ApiError(detail, reponse.status);
  }
}

export async function modifierRegle(
  regleId: string,
  maj: Partial<Pick<RegleRappel, "message" | "canaux" | "portee" | "dossier_ids" | "declencheur" | "jours_avant" | "actif">>,
): Promise<void> {
  const reponse = await requeteGestionnaire(`/regles-rappel/${regleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(maj),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? "Impossible de modifier la règle.", reponse.status);
  }
}

export async function supprimerRegle(regleId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/regles-rappel/${regleId}`, { method: "DELETE" });
  if (!reponse.ok) {
    throw new ApiError("Impossible de supprimer la règle.", reponse.status);
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

export async function retirerMembre(email: string): Promise<void> {
  const reponse = await requeteGestionnaire("/portefeuille/membres", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(corps.detail ?? "Impossible de retirer cet accès.", reponse.status);
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

export async function renvoyerInvitation(dossierId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/invitation/renvoyer`, {
    method: "POST",
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(corps.detail ?? "Impossible de renvoyer l'invitation.", reponse.status);
  }
}

export async function annulerInvitation(dossierId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/invitation`, {
    method: "DELETE",
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(corps.detail ?? "Impossible d'annuler l'invitation.", reponse.status);
  }
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

// --- Tags d'entreprises et exclusions (AXE-829) ---

async function lireReglageTags(reponse: Response, message: string): Promise<ReglageTags> {
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? message, reponse.status);
  }
  return (await reponse.json()) as ReglageTags;
}

export async function lireTags(): Promise<ReglageTags> {
  return lireReglageTags(await requeteGestionnaire("/tags"), "Impossible de lire les tags.");
}

export async function creerTag(nom: string, description = ""): Promise<ReglageTags> {
  const reponse = await requeteGestionnaire("/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nom, description }),
  });
  return lireReglageTags(reponse, "Impossible de créer ce tag.");
}

/** Pose (ou retire, `pose` à false) un tag sur un ou plusieurs dossiers. */
export async function poserTag(tag: string, dossierIds: string[], pose = true): Promise<void> {
  const reponse = await requeteGestionnaire(`/tags/${encodeURIComponent(tag)}/dossiers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dossier_ids: dossierIds, pose }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? "Le tag n'a pas été posé.", reponse.status);
  }
}

export async function reglerExclusion(traitement: string, tags: string[]): Promise<ReglageTags> {
  const reponse = await requeteGestionnaire(`/tags/exclusions/${encodeURIComponent(traitement)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags }),
  });
  return lireReglageTags(reponse, "Le réglage n'a pas été enregistré.");
}

// --- Opérations déjà classées (AXE-823) ---

export async function lireClassees(params: URLSearchParams): Promise<OperationsClassees> {
  const reponse = await requeteGestionnaire(`/expert/classees?${params.toString()}`);
  if (reponse.status === 401) throw new ErreurAuthGestionnaire();
  if (!reponse.ok) {
    throw new ApiError("Impossible de charger les opérations classées.", reponse.status);
  }
  return (await reponse.json()) as OperationsClassees;
}

export async function noterVerdict(
  dossierId: string,
  ecritureId: string,
  verdict: "juste" | "faux",
): Promise<void> {
  const reponse = await requeteGestionnaire("/expert/classees/verdict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dossier_id: dossierId, ecriture_id: ecritureId, verdict }),
  });
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? "Le verdict n'a pas été enregistré.", reponse.status);
  }
}

// --- Quarantaine d'ingestion (AXE-424) ---

export async function listerQuarantaine(dossierId: string): Promise<EntreeQuarantaine[]> {
  const reponse = await requeteGestionnaire(`/dossiers/${dossierId}/quarantaine`);
  if (!reponse.ok) {
    throw new ApiError("Impossible de lire les opérations à revoir.", reponse.status);
  }
  return (await reponse.json()) as EntreeQuarantaine[];
}

export async function resoudreQuarantaine(
  dossierId: string,
  entreeId: string,
  decision: "accepter" | "ignorer",
): Promise<EntreeQuarantaine> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${dossierId}/quarantaine/${encodeURIComponent(entreeId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    },
  );
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? "L'opération n'a pas été traitée.", reponse.status);
  }
  return (await reponse.json()) as EntreeQuarantaine;
}

// --- Synchronisation et nouveaux chauffeurs Digifactory (AXE-845) ---

async function lireJson<T>(reponse: Response, message: string): Promise<T> {
  if (!reponse.ok) {
    const corps = (await reponse.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(corps?.detail ?? message, reponse.status);
  }
  return (await reponse.json()) as T;
}

export async function lireSynchronisation(): Promise<Synchronisation | null> {
  return lireJson(await requeteGestionnaire("/portefeuille/synchronisation"), "Suivi indisponible.");
}

export async function lancerSynchronisation(): Promise<Synchronisation> {
  return lireJson(
    await requeteGestionnaire("/portefeuille/synchroniser", { method: "POST" }),
    "La synchronisation n'a pas pu être lancée.",
  );
}

export async function listerNouveauxChauffeurs(): Promise<NouveauChauffeur[]> {
  return lireJson(
    await requeteGestionnaire("/portefeuille/nouveaux-chauffeurs"),
    "Impossible de lire les nouveaux chauffeurs.",
  );
}

export async function deciderNouveauxChauffeurs(
  contactNrs: string[],
  decision: "ajouter" | "ignorer" | "reprendre",
): Promise<NouveauChauffeur[]> {
  return lireJson(
    await requeteGestionnaire("/portefeuille/nouveaux-chauffeurs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_nrs: contactNrs, decision }),
    }),
    "La décision n'a pas été enregistrée.",
  );
}


// --- Création des dossiers depuis un fichier (AXE-809) ---

export type LigneImport = {
  numero: number;
  dossier_id: string | null;
  nom: string | null;
  erreurs: string[];
  avertissements: string[];
};

export type RapportImport = {
  lignes: LigneImport[];
  a_creer: number;
  en_erreur: number;
  creation: Synchronisation | null;
};

function corpsFichier(fichier: File): FormData {
  const corps = new FormData();
  corps.append("fichier", fichier);
  return corps;
}

/** Le rapport ligne par ligne ; rien n'est créé. */
export async function verifierImport(fichier: File, sirene: boolean): Promise<RapportImport> {
  return lireJson(
    await requeteGestionnaire(`/portefeuille/import-dossiers/rapport?sirene=${sirene}`, {
      method: "POST",
      body: corpsFichier(fichier),
    }),
    "Le fichier n'a pas pu être vérifié.",
  );
}

/** Admin : confie les lignes valides au worker, qui les crée en un lot. */
export async function importerDossiers(fichier: File): Promise<RapportImport> {
  return lireJson(
    await requeteGestionnaire("/portefeuille/import-dossiers", {
      method: "POST",
      body: corpsFichier(fichier),
    }),
    "L'import n'a pas pu être lancé.",
  );
}

export async function suivreImport(): Promise<Synchronisation | null> {
  return lireJson(await requeteGestionnaire("/portefeuille/import-dossiers"), "Suivi indisponible.");
}

export async function telechargerModeleImport(): Promise<Blob> {
  const reponse = await requeteGestionnaire("/portefeuille/import-dossiers/modele.csv");
  if (!reponse.ok) throw new ApiError("Modèle indisponible.", reponse.status);
  return reponse.blob();
}

/** AXE-804 : l'expert-comptable habilité reprend le bilan d'ouverture d'un
 * dossier de sa lettre de mission, avec un motif. */
export async function lireOuvertureExpert(dossierId: string): Promise<OuvertureVue> {
  return lireJson(
    await requeteGestionnaire(`/expert/dossiers/${dossierId}/ouverture`),
    "Le bilan d'ouverture n'a pas pu être lu.",
  );
}

function corpsFec(fichier: File, champs: Record<string, string>): FormData {
  const corps = corpsFichier(fichier);
  for (const [nom, valeur] of Object.entries(champs)) corps.append(nom, valeur);
  return corps;
}

export async function analyserFecExpert(
  dossierId: string,
  fichier: File,
  correspondance: string,
): Promise<AnalyseFec> {
  return lireJson(
    await requeteGestionnaire(`/expert/dossiers/${dossierId}/ouverture/fec/analyse`, {
      method: "POST",
      body: corpsFec(fichier, { correspondance }),
    }),
    "Le FEC n'a pas pu être analysé.",
  );
}

export async function reprendreFecExpert(
  dossierId: string,
  fichier: File,
  champs: { correspondance: string; attestation: string; deficits_euros: string; motif: string },
): Promise<OuvertureVue> {
  return lireJson(
    await requeteGestionnaire(`/expert/dossiers/${dossierId}/ouverture/fec`, {
      method: "POST",
      body: corpsFec(fichier, champs),
    }),
    "Le bilan d'ouverture n'a pas pu être repris.",
  );
}


/** AXE-911 : comptes Rollee à relier, état du lien de chaque entreprise. */
export async function lireRolleePortefeuille(): Promise<RolleePortefeuille> {
  const reponse = await requeteGestionnaire("/portefeuille/rollee");
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as RolleePortefeuille;
}

/** AXE-918 : relier les comptes Rollee sans attendre la nuit (job du worker). */
export async function lancerRapprochementRollee(): Promise<PassageRollee> {
  const reponse = await requeteGestionnaire("/portefeuille/rollee/rapprocher", { method: "POST" });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as PassageRollee;
}

export async function lireRapprochementRollee(): Promise<PassageRollee | null> {
  const reponse = await requeteGestionnaire("/portefeuille/rollee/rapprochement");
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as PassageRollee | null;
}

/** `dossierId` à null : « aucun de ces comptes ». */
export async function choisirCompteRollee(rolleeUserId: string, dossierId: string | null): Promise<void> {
  const reponse = await requeteGestionnaire("/portefeuille/rollee/choix", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rollee_user_id: rolleeUserId, dossier_id: dossierId }),
  });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
}

/** AXE-919 : chercher un user Rollee par son nom, tous comptes Rollee confondus. */
export async function chercherCompteRollee(requete: string): Promise<FicheAnnuaireRollee[]> {
  const reponse = await requeteGestionnaire(`/portefeuille/rollee/annuaire?q=${encodeURIComponent(requete)}`);
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as FicheAnnuaireRollee[];
}

export async function lierCompteRollee(dossierId: string, rolleeUserId: string): Promise<void> {
  const reponse = await requeteGestionnaire(`/dossiers/${encodeURIComponent(dossierId)}/rollee/lier`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rollee_user_id: rolleeUserId }),
  });
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
}

export async function lireLienRollee(dossierId: string): Promise<FicheRollee> {
  const reponse = await requeteGestionnaire(`/dossiers/${encodeURIComponent(dossierId)}/rollee`);
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return (await reponse.json()) as FicheRollee;
}

export async function delierRollee(dossierId: string, motif: string): Promise<number> {
  const reponse = await requeteGestionnaire(
    `/dossiers/${encodeURIComponent(dossierId)}/rollee/delier`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motif }),
    },
  );
  if (!reponse.ok) throw erreurApi(await lireCorps(reponse), reponse);
  return ((await reponse.json()) as { versements_contrepasses: number }).versements_contrepasses;
}
