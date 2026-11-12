/** Piège à focus d'une fenêtre modale : où envoyer le focus quand Tab ou
 * Maj+Tab va sortir de la fenêtre. Logique pure, sans DOM, pour être testée.
 *
 * `nombre` : éléments focalisables dans la fenêtre. `courant` : index de celui
 * qui a le focus, ou -1 si le focus est ailleurs (la fenêtre elle-même, ou
 * hors d'elle). Renvoie l'index à focaliser de force, ou `null` quand le
 * navigateur peut suivre son ordre naturel (milieu de la fenêtre). */
export function indexFocusPiege(nombre: number, courant: number, retour: boolean): number | null {
  if (nombre === 0) return null;
  if (courant === -1) return retour ? nombre - 1 : 0;
  if (retour && courant === 0) return nombre - 1;
  if (!retour && courant === nombre - 1) return 0;
  return null;
}
