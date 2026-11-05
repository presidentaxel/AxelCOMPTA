/** Messages d'authentification montrés à la personne.
 *
 * Supabase Auth répond en anglais (`error_code`, `msg`, `error_description`).
 * Ce module est la seule traduction : la phrase affichée est en français et
 * dit quoi faire ensuite. Les formes couvertes sont celles de l'API GoTrue :
 * identifiants refusés, lien déjà ouvert (un logiciel de messagerie peut
 * consommer le jeton avant la personne), mot de passe trop court ou trop
 * connu, et adresse inconnue quand le lien magique est demandé avec
 * `create_user: false` (réponse `otp_disabled`, qui ne doit pas contredire
 * le message neutre).
 */

export const LONGUEUR_MIN_MOT_DE_PASSE = 8;

export const INDICATION_MOT_DE_PASSE = "Au moins 8 caractères.";

export const MESSAGE_RESEAU =
  "La connexion a échoué. Vérifiez votre réseau, puis réessayez.";

export const MESSAGE_IDENTIFIANTS =
  "Adresse ou mot de passe incorrect. Réessayez, ou utilisez « Mot de passe oublié ».";

export const MESSAGE_LIEN_EXPIRE =
  "Ce lien a expiré ou a déjà été ouvert. Demandez un nouveau lien, ou réinitialisez votre mot de passe.";

export const MESSAGE_INVITATION =
  "Cette invitation a expiré ou a déjà été ouverte. Connectez-vous si vous avez un mot de passe, sinon demandez à votre gestionnaire de la renvoyer.";

export const MESSAGE_MOT_DE_PASSE_COURT = `Choisissez un mot de passe d'au moins ${LONGUEUR_MIN_MOT_DE_PASSE} caractères.`;

export const MESSAGE_MOT_DE_PASSE_FAIBLE =
  "Ce mot de passe est trop facile à deviner. Choisissez-en un autre, d'au moins 8 caractères.";

export const MESSAGE_MEME_MOT_DE_PASSE =
  "Choisissez un mot de passe différent de l'actuel.";

export const MESSAGE_EMAIL_NON_CONFIRME =
  "Cette adresse n'est pas encore confirmée. Ouvrez l'invitation reçue, ou demandez un nouveau lien.";

export const MESSAGE_TROP_DE_TENTATIVES =
  "Trop de tentatives. Patientez une minute, puis réessayez.";

export const MESSAGE_TROP_D_EMAILS =
  "Un e-mail vient d'être envoyé. Patientez une minute avant d'en demander un autre.";

export const MESSAGE_SESSION = "Votre session a expiré. Reconnectez-vous.";

export const MESSAGE_GENERIQUE =
  "L'authentification a échoué. Réessayez, ou demandez un nouveau lien.";

export const MESSAGE_SERVICE =
  "Le service d'authentification ne répond pas. Réessayez dans un instant.";

export const MESSAGE_SANS_DOSSIER =
  "Ce compte n'est lié à aucun dossier. Demandez une invitation à votre gestionnaire.";

export const MESSAGE_SANS_LIEN =
  "Ce compte n'est lié ni à un dossier ni à un portefeuille. Reconnectez-vous avec le bon compte, ou demandez un accès.";

export const MESSAGE_SANS_PORTEFEUILLE =
  "Ce compte n'est lié à aucun portefeuille. Reconnectez-vous avec le compte du cabinet, ou demandez un accès.";

export const MESSAGE_LIEN_INCOMPLET =
  "Ce lien ne peut pas être terminé ici. Demandez un nouveau lien, ou réinitialisez votre mot de passe.";

const PAR_CODE: Record<string, string> = {
  invalid_credentials: MESSAGE_IDENTIFIANTS,
  invalid_grant: MESSAGE_IDENTIFIANTS,
  user_not_found: MESSAGE_IDENTIFIANTS,
  otp_disabled: MESSAGE_GENERIQUE,
  email_not_confirmed: MESSAGE_EMAIL_NON_CONFIRME,
  otp_expired: MESSAGE_LIEN_EXPIRE,
  flow_state_expired: MESSAGE_LIEN_EXPIRE,
  flow_state_not_found: MESSAGE_LIEN_EXPIRE,
  access_denied: MESSAGE_LIEN_EXPIRE,
  bad_code_verifier: MESSAGE_LIEN_EXPIRE,
  bad_jwt: MESSAGE_LIEN_EXPIRE,
  invite_not_found: MESSAGE_INVITATION,
  over_request_rate_limit: MESSAGE_TROP_DE_TENTATIVES,
  over_email_send_rate_limit: MESSAGE_TROP_D_EMAILS,
  over_sms_send_rate_limit: MESSAGE_TROP_D_EMAILS,
  same_password: MESSAGE_MEME_MOT_DE_PASSE,
  session_expired: MESSAGE_SESSION,
  session_not_found: MESSAGE_SESSION,
  refresh_token_not_found: MESSAGE_SESSION,
  refresh_token_already_used: MESSAGE_SESSION,
  request_timeout: MESSAGE_SERVICE,
  unexpected_failure: MESSAGE_SERVICE,
  user_banned: "Ce compte est désactivé. Contactez votre gestionnaire.",
  email_provider_disabled:
    "L'envoi d'e-mail est indisponible. Réessayez plus tard, ou connectez-vous avec votre mot de passe.",
};

type CorpsAuth = {
  error?: string;
  error_code?: string;
  error_description?: string;
  msg?: string;
  message?: string;
  weak_password?: { reasons?: string[]; message?: string };
};

export function messageMotDePasseCourt(motDePasse: string): string | null {
  if (motDePasse.length < LONGUEUR_MIN_MOT_DE_PASSE) return MESSAGE_MOT_DE_PASSE_COURT;
  return null;
}

/** Adresse inconnue pour un envoi qui ne doit pas dire si le compte existe
 * (lien magique `create_user: false`, réinitialisation). */
export function absenceDeCompte(corps: unknown): boolean {
  const code = codeDe(corps);
  if (code === "otp_disabled" || code === "user_not_found") return true;
  const texte = texteDe(corps).toLowerCase();
  return texte.includes("signups not allowed for otp") || texte.includes("user not found");
}

export function traduireCorpsAuth(corps: unknown, statut = 0): string {
  const faible = messageMotDePasseFaible(corps);
  if (faible) return faible;
  const code = codeDe(corps);
  const connu = code ? PAR_CODE[code] : undefined;
  if (connu) return connu;
  const parTexte = traduireTexteAuth(texteDe(corps));
  if (parTexte) return parTexte;
  if (statut === 429) return MESSAGE_TROP_DE_TENTATIVES;
  if (statut >= 500 || statut === 0) return MESSAGE_SERVICE;
  if (statut === 401 || statut === 403) return MESSAGE_LIEN_EXPIRE;
  return MESSAGE_GENERIQUE;
}

export function traduireExceptionAuth(exception: unknown): string {
  if (!(exception instanceof Error)) return MESSAGE_GENERIQUE;
  if (exception.name === "ErreurAuthChauffeur" || exception.name === "ErreurAuthGestionnaire") {
    return exception.message;
  }
  if (exception instanceof TypeError || estMessageReseau(exception.message)) {
    return MESSAGE_RESEAU;
  }
  return traduireTexteAuth(exception.message) ?? MESSAGE_GENERIQUE;
}

/** Erreur déjà posée dans l'URL par Supabase (fragment ou query), ou `null`
 * si ce n'est pas un échec de lien. */
export function messageParametresAuth(parametres: URLSearchParams): string | null {
  if (!parametres.get("error") && !parametres.get("error_code") && !parametres.get("error_description")) {
    return null;
  }
  return traduireCorpsAuth(
    {
      error: parametres.get("error") ?? undefined,
      error_code: parametres.get("error_code") ?? undefined,
      error_description: parametres.get("error_description") ?? undefined,
    },
    400,
  );
}

function messageMotDePasseFaible(corps: unknown): string | null {
  const recu = commeCorps(corps);
  const raisons = recu.weak_password?.reasons ?? [];
  const texte = texteDe(corps).toLowerCase();
  const code = codeDe(corps);
  const concerne =
    code === "weak_password" ||
    raisons.length > 0 ||
    texte.includes("known to be weak") ||
    texte.includes("easy to guess") ||
    texte.includes("password should be at least");
  if (!concerne) return null;
  if (raisons.includes("pwned") || texte.includes("known to be weak") || texte.includes("easy to guess")) {
    return MESSAGE_MOT_DE_PASSE_FAIBLE;
  }
  return messageLongueurServeur(texte);
}

function messageLongueurServeur(texte: string): string {
  const trouve = texte.match(/at least (\d+) character/);
  const demande = trouve ? Number(trouve[1]) : LONGUEUR_MIN_MOT_DE_PASSE;
  const longueur = Math.max(LONGUEUR_MIN_MOT_DE_PASSE, demande);
  if (longueur === LONGUEUR_MIN_MOT_DE_PASSE) return MESSAGE_MOT_DE_PASSE_COURT;
  return `Choisissez un mot de passe d'au moins ${longueur} caractères.`;
}

/** Reconnaît l'anglais connu. `null` : rien à traduire (déjà traité, ou texte
 * qui ne doit pas fuir tel quel — l'appelant met alors le message générique). */
export function traduireTexteAuth(texte: string): string | null {
  const brut = texte.toLowerCase();
  if (estMessageReseau(brut)) return MESSAGE_RESEAU;
  if (brut.includes("invalid login credentials") || brut.includes("invalid grant")) {
    return MESSAGE_IDENTIFIANTS;
  }
  if (brut.includes("email not confirmed")) return MESSAGE_EMAIL_NON_CONFIRME;
  if (
    brut.includes("email link is invalid") ||
    brut.includes("has expired") ||
    brut.includes("invalid token") ||
    brut.includes("one-time token not found") ||
    brut.includes("already been used")
  ) {
    return MESSAGE_LIEN_EXPIRE;
  }
  if (brut.includes("known to be weak") || brut.includes("easy to guess") || brut.includes("pwned")) {
    return MESSAGE_MOT_DE_PASSE_FAIBLE;
  }
  if (brut.includes("password should be at least") || brut.includes("password is too short")) {
    return messageLongueurServeur(brut);
  }
  if (brut.includes("different from the old")) return MESSAGE_MEME_MOT_DE_PASSE;
  if (brut.includes("rate limit") || brut.includes("only request this")) {
    return brut.includes("email") || brut.includes("60") ? MESSAGE_TROP_D_EMAILS : MESSAGE_TROP_DE_TENTATIVES;
  }
  return null;
}

function estMessageReseau(texte: string): boolean {
  const brut = texte.toLowerCase();
  return (
    brut.includes("failed to fetch") ||
    brut.includes("networkerror") ||
    brut.includes("network error") ||
    brut.includes("load failed") ||
    brut.includes("fetch failed") ||
    brut.includes("failed to parse url") ||
    brut.includes("network request failed") ||
    brut.includes("internet connection appears to be offline")
  );
}

function commeCorps(valeur: unknown): CorpsAuth {
  if (typeof valeur !== "object" || valeur === null) return {};
  return valeur as CorpsAuth;
}

function codeDe(valeur: unknown): string {
  const corps = commeCorps(valeur);
  return (corps.error_code ?? corps.error ?? "").trim().toLowerCase();
}

function texteDe(valeur: unknown): string {
  const corps = commeCorps(valeur);
  return [corps.error_description, corps.msg, corps.message, corps.weak_password?.message]
    .filter((partie): partie is string => typeof partie === "string" && partie.length > 0)
    .join(" ");
}
