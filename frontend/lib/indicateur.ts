/** Mouvement de l'indicateur glissant (onglets, barre de navigation).
 *
 * Mesuré sur la vidéo de référence (poignée de bloc d'un éditeur) : un saut de
 * 350 px s'y fait en cinq images à 30 i/s, soit environ 170 ms, avec une vitesse
 * qui monte puis retombe, sans jamais s'arrêter net ni disparaître. D'où une
 * durée de 180 ms et une courbe qui freine en fin de course. C'est la seule
 * exception à la règle « transitions de 150 ms au plus » (DESIGN.md) : un
 * déplacement a besoin d'un peu plus de temps qu'un changement de couleur. */
export const DUREE_GLISSEMENT_MS = 180;
export const COURBE_GLISSEMENT = "cubic-bezier(0.22, 1, 0.36, 1)";

export type Rect = { left: number; width: number };

/** Où poser l'indicateur : décalage horizontal et largeur de l'élément actif,
 * relatifs au conteneur. Arrondi au demi-pixel pour éviter un filet flou. */
export function positionIndicateur(conteneur: Pick<Rect, "left">, actif: Rect): { x: number; largeur: number } {
  const demi = (valeur: number) => Math.round(valeur * 2) / 2;
  return { x: demi(actif.left - conteneur.left), largeur: demi(actif.width) };
}

/** Durée à appliquer : aucune au premier placement (l'indicateur ne doit pas
 * glisser depuis zéro au chargement) ni quand l'utilisateur réduit les
 * animations. */
export function dureeGlissement(premierPlacement: boolean, mouvementReduit: boolean): number {
  return premierPlacement || mouvementReduit ? 0 : DUREE_GLISSEMENT_MS;
}
