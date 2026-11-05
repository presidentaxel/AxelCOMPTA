import { MESSAGE_SERVEUR_INJOIGNABLE } from "./session";

const RESEAU = /failed to fetch|networkerror|load failed|network request failed|fetch failed/;
const IDENTIFIANTS = /invalid login|invalid_credentials|invalid email or password|email ou mot de passe/;
const ADRESSE_INCONNUE = /signups not allowed|user not found|user_not_found|otp_disabled|user banned/;
const COURRIEL_NON_CONFIRME = /email not confirmed|email_not_confirmed/;
const TROP_DE_TENTATIVES = /rate limit|over_request_rate|too many requests|over_email_send/;
const MOT_DE_PASSE_FAIBLE = /weak password|password should be at least|at least 6|at least 8/;
const LIEN_EXPIRE = /expired|invalid grant|otp_expired|flow_state_expired|access_denied/;

export const MOT_DE_PASSE_MIN = 8;

export function motDePasseAcceptable(motDePasse: string): string | null {
  if (motDePasse.length < MOT_DE_PASSE_MIN) {
    return `Le mot de passe doit contenir au moins ${MOT_DE_PASSE_MIN} caractères.`;
  }
  return null;
}

/** Les erreurs Supabase restent en anglais : on les traduit avant affichage.
 * Une adresse inconnue sur un lien magique reste neutre (pas d'aveu). */
export function messageAuthFrancais(brut: string, statut?: number): string {
  const texte = brut.toLowerCase();
  if (RESEAU.test(texte) || statut === 0) {
    return MESSAGE_SERVEUR_INJOIGNABLE;
  }
  if (IDENTIFIANTS.test(texte)) {
    return "Adresse ou mot de passe incorrect.";
  }
  if (COURRIEL_NON_CONFIRME.test(texte)) {
    return "Confirmez votre adresse e-mail avant de vous connecter.";
  }
  if (TROP_DE_TENTATIVES.test(texte) || statut === 429) {
    return "Trop de tentatives. Réessayez dans un instant.";
  }
  if (MOT_DE_PASSE_FAIBLE.test(texte)) {
    return `Le mot de passe doit contenir au moins ${MOT_DE_PASSE_MIN} caractères.`;
  }
  if (LIEN_EXPIRE.test(texte)) {
    return "Ce lien est invalide ou expiré. Demandez-en un nouveau.";
  }
  if (ADRESSE_INCONNUE.test(texte)) {
    return "Si un compte existe pour cette adresse, le lien est envoyé.";
  }
  if (statut !== undefined && statut >= 500) {
    return "Le service de connexion ne répond pas. Réessayez dans un instant.";
  }
  return "La connexion n'a pas abouti. Réessayez, ou demandez un nouveau lien.";
}

export function adresseInconnue(brut: string): boolean {
  return ADRESSE_INCONNUE.test(brut.toLowerCase());
}
