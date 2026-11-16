/** Le formulaire « Demander un échange » de la page publique (AXE-949).
 *
 * Les phrases d'erreur sont celles du serveur (`prospection/models.py`) : le
 * serveur reste la référence, ce contrôle évite seulement un aller-retour.
 * Pas de logique de rôle ni de limite de débit ici : le serveur décide. */

export type Profil = "cabinet" | "centrale";

export type SaisieEchange = {
  nom: string;
  email: string;
  organisation: string;
  profil: Profil | "";
  message: string;
  /** Champ piège : invisible, une personne ne le remplit jamais. */
  siteWeb: string;
};

export const SAISIE_VIDE: SaisieEchange = {
  nom: "",
  email: "",
  organisation: "",
  profil: "",
  message: "",
  siteWeb: "",
};

export type ChampEchange = "nom" | "email" | "organisation" | "profil" | "message";

export type ErreurSaisie = { champ: ChampEchange; message: string };

export const LONGUEUR_MAX: Record<Exclude<ChampEchange, "profil">, number> = {
  nom: 100,
  email: 254,
  organisation: 150,
  message: 2000,
};

const LIBELLES: Record<Exclude<ChampEchange, "profil">, string> = {
  nom: "nom",
  email: "e-mail",
  organisation: "organisation",
  message: "message",
};

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/u;

/** La première erreur de la saisie, dans l'ordre du formulaire, ou `null`. */
export function premiereErreur(saisie: SaisieEchange): ErreurSaisie | null {
  const nom = saisie.nom.trim();
  const email = saisie.email.trim();
  const organisation = saisie.organisation.trim();
  if (nom === "") return { champ: "nom", message: "Indiquez votre nom." };
  if (!EMAIL.test(email)) return { champ: "email", message: "Indiquez une adresse e-mail valide." };
  if (organisation === "") return { champ: "organisation", message: "Indiquez votre organisation." };
  if (saisie.profil === "") {
    return { champ: "profil", message: "Indiquez si vous êtes un cabinet ou une centrale." };
  }
  const valeurs = { nom, email, organisation, message: saisie.message.trim() };
  for (const champ of Object.keys(valeurs) as (keyof typeof valeurs)[]) {
    if (valeurs[champ].length > LONGUEUR_MAX[champ]) {
      return {
        champ,
        message: `Le champ « ${LIBELLES[champ]} » est trop long (${LONGUEUR_MAX[champ]} caractères au plus).`,
      };
    }
  }
  return null;
}

/** Le corps attendu par `POST /demandes-echange`. */
export function corpsDeLaDemande(saisie: SaisieEchange): Record<string, string | null> {
  const message = saisie.message.trim();
  return {
    nom: saisie.nom.trim(),
    email: saisie.email.trim(),
    organisation: saisie.organisation.trim(),
    role: saisie.profil,
    message: message === "" ? null : message,
    site_web: saisie.siteWeb,
  };
}

export type ResultatEnvoi =
  | { statut: "envoyee"; message: string }
  | { statut: "refusee"; champ: ChampEchange | null; message: string }
  | { statut: "injoignable"; message: string };

export const MESSAGE_INJOIGNABLE = "Le serveur ne répond pas. Réessayez dans un instant.";
const MESSAGE_PAR_DEFAUT = "La demande n'a pas pu être envoyée. Réessayez dans un instant.";

function phrase(valeur: unknown): string | null {
  return typeof valeur === "string" && valeur.trim() !== "" ? valeur : null;
}

/** Le champ que la phrase du serveur met en cause, pour y poser l'erreur. */
export function champDeLaPhrase(message: string): ChampEchange | null {
  if (/votre nom|« nom »/u.test(message)) return "nom";
  if (/e-mail/u.test(message)) return "email";
  if (/organisation/u.test(message)) return "organisation";
  if (/cabinet ou une centrale/u.test(message)) return "profil";
  if (/« message »/u.test(message)) return "message";
  return null;
}

/** Ce que dit l'écran après la réponse du serveur. `detail` n'est repris que
 * s'il est une phrase : sur un corps démesuré FastAPI renvoie une liste
 * d'erreurs de validation, qui ne doit jamais arriver à l'écran. */
export function resultatApresReponse(
  statutHttp: number,
  corps: { message?: unknown; detail?: unknown },
): ResultatEnvoi {
  if (statutHttp >= 200 && statutHttp < 300) {
    return { statut: "envoyee", message: phrase(corps.message) ?? "Merci, nous revenons vers vous." };
  }
  const detail = phrase(corps.detail);
  const message = detail ?? MESSAGE_PAR_DEFAUT;
  return { statut: "refusee", champ: detail === null ? null : champDeLaPhrase(detail), message };
}

export async function envoyerLaDemande(
  saisie: SaisieEchange,
  base: string,
  appel: typeof fetch = fetch,
): Promise<ResultatEnvoi> {
  try {
    const reponse = await appel(`${base}/demandes-echange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpsDeLaDemande(saisie)),
    });
    const corps = (await reponse.json().catch(() => ({}))) as { message?: unknown; detail?: unknown };
    return resultatApresReponse(reponse.status, corps);
  } catch {
    return { statut: "injoignable", message: MESSAGE_INJOIGNABLE };
  }
}
