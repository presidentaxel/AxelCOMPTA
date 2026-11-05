/** Au-delà, on considère qu'un clavier virtuel couvre le bas de l'écran.
 * La barre d'adresse mobile reste en dessous de ce seuil. */
export const SEUIL_CLAVIER_PX = 150;

/** Écart entre la plus grande fenêtre vue sans clavier et le visual
 * viewport. `plein` ne doit pas rétrécir quand le clavier s'ouvre, sinon
 * l'inset retombe à 0 sur les navigateurs qui réduisent aussi `innerHeight`. */
export function insetClavier(plein: number, hauteurVisible: number, decalage: number): number {
  return Math.max(0, Math.round(plein - hauteurVisible - decalage));
}

export function clavierOuvert(inset: number): boolean {
  return inset > SEUIL_CLAVIER_PX;
}
