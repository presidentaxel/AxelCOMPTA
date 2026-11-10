/** Message déposé quand une session du mauvais côté est effacée.
 * Il doit rester jusqu'à l'affichage du formulaire, même si un second
 * renvoi vers `/connexion` a lieu dans la foulée. */

const CLE_MESSAGE_CONNEXION = "axelcompta_message_connexion";

export function laisserMessageConnexion(message: string): void {
  try {
    window.sessionStorage.setItem(CLE_MESSAGE_CONNEXION, message);
  } catch {
    // Stockage indisponible : la redirection a lieu quand même.
  }
}

export function messageConnexionEnAttente(): string | null {
  try {
    return window.sessionStorage.getItem(CLE_MESSAGE_CONNEXION);
  } catch {
    return null;
  }
}

export function prendreMessageConnexion(): string | null {
  const message = messageConnexionEnAttente();
  if (!message) return null;
  try {
    window.sessionStorage.removeItem(CLE_MESSAGE_CONNEXION);
  } catch {
    // Le message a été lu, même s'il reste affiché au prochain passage.
  }
  return message;
}
