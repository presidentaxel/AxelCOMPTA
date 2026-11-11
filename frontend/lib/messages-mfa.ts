/** Messages de la double authentification montrés à la personne.
 *
 * `lib/mfa.ts` relaie le `msg` de Supabase tel quel : en anglais, et parfois
 * technique (« Invalid TOTP code entered »). Ce module est la seule
 * traduction de l'écran. Il ne dit jamais plus qu'un code incorrect : rien
 * qui indique l'état du compte ou du facteur. */

import { MESSAGE_RESEAU, MESSAGE_TROP_DE_TENTATIVES, traduireTexteAuth } from "./messages-auth";

export const MESSAGE_CODE_INCORRECT =
  "Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.";

export const MESSAGE_PREPARATION =
  "Impossible de préparer la double authentification. Réessayez dans un instant.";

/** Les messages de repli français de `lib/mfa.ts` (« Impossible de lire votre compte. »,
 * « Code incorrect. … ») sont déjà bons : on les garde tels quels. */
const REPLI_FRANCAIS = /^(Impossible de |Code incorrect)/;

export type PhaseMfa = "preparation" | "verification";

/** La phrase à montrer pour une exception levée par `lib/mfa.ts`. À la
 * vérification, tout échec inconnu se dit « code incorrect » : le refus du
 * serveur n'en dit pas plus, et l'action de reprise est la même. */
export function messageErreurMfa(exception: unknown, phase: PhaseMfa): string {
  const repli = phase === "verification" ? MESSAGE_CODE_INCORRECT : MESSAGE_PREPARATION;
  if (!(exception instanceof Error)) return repli;
  if (exception instanceof TypeError) return MESSAGE_RESEAU;
  if (REPLI_FRANCAIS.test(exception.message)) return exception.message;
  const traduit = traduireTexteAuth(exception.message);
  if (phase === "verification") {
    return traduit === MESSAGE_RESEAU || traduit === MESSAGE_TROP_DE_TENTATIVES ? traduit : repli;
  }
  return traduit ?? repli;
}
