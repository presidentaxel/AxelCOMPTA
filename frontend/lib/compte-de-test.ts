/** Compte de test (AXE-822) : il lit l'espace chauffeur de n'importe quel
 * dossier de son portefeuille, en lecture seule, jusqu'à sa date de fin.
 * Exception de la période de test, retirée avant que les chauffeurs se
 * connectent. Le serveur vérifie tout (`api/routes.py`, `get_identite`) : ces
 * fonctions ne font que choisir l'adresse et l'en-tête. */

export const ROLE_LECTEUR_TEST = "lecteur_tous_dossiers";
export const PAGE_CHOIX_DOSSIER = "/chauffeur/test";

type Metadata = { dossier_id?: unknown; role_test?: unknown };

/** Les liens d'un jeton : le dossier du chauffeur, ou le compte de test
 * (dossier choisi plus tard). `null` si le jeton n'ouvre aucun des deux. */
export function liensDuJeton(
  appMetadata: unknown,
): { dossierId: string; lecteurTest: boolean } | null {
  const metadata = (appMetadata ?? {}) as Metadata;
  if (metadata.role_test === ROLE_LECTEUR_TEST) return { dossierId: "", lecteurTest: true };
  if (typeof metadata.dossier_id === "string" && metadata.dossier_id) {
    return { dossierId: metadata.dossier_id, lecteurTest: false };
  }
  return null;
}

type SessionLiens = { dossierId: string; lecteurTest?: boolean };

/** Où aller une fois connecté : son dossier, ou l'écran « Quel dossier ? ». */
export function cheminDuDossier(session: SessionLiens): string {
  if (session.lecteurTest && !session.dossierId) return PAGE_CHOIX_DOSSIER;
  return `/chauffeur/${session.dossierId}`;
}

/** L'en-tête `X-Dossier`, pour le compte de test seulement. */
export function avecDossierDeTest(init: RequestInit, session: SessionLiens | null): RequestInit {
  if (!session?.lecteurTest || !session.dossierId) return init;
  const entetes = new Headers(init.headers);
  entetes.set("X-Dossier", session.dossierId);
  return { ...init, headers: entetes };
}
