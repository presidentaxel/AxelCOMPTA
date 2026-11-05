/** Saisie chauffeur : montants en centimes, et garde avant d'écrire une liste
 * déjà enregistrée. Une lecture ratée ne doit jamais devenir une liste vide
 * qu'on renverrait ensuite. */

export type LectureListe<T> =
  | { statut: "en_cours" }
  | { statut: "pret"; lignes: T[] }
  | { statut: "erreur"; message: string };

const ESPACES = /[\s\u00a0\u202f]/g;

/** « 1 000,50 », « 1000.50 » et l'espace insécable. Vide et illisible
 * sont des refus, jamais zéro. */
export function lireEuros(
  saisie: string,
): { centimes: number } | { message: string } {
  const texte = saisie.replace(ESPACES, "").replace(",", ".");
  if (texte === "") {
    return { message: "Indiquez un montant." };
  }
  const morceaux = /^(\d+)(?:\.(\d{1,2}))?$/.exec(texte);
  if (morceaux === null) {
    return { message: "Écrivez le montant avec une virgule, par exemple 1 000,50." };
  }
  const cents = (morceaux[2] ?? "").padEnd(2, "0");
  const centimes = Number(morceaux[1]) * 100 + Number(cents);
  if (centimes <= 0) {
    return { message: "Indiquez un montant supérieur à zéro." };
  }
  return { centimes };
}

/** La liste à envoyer, ou `null` si la lecture n'a pas réussi : aucun
 * enregistrement ne part. */
export function listeAEnregistrer<T>(lecture: LectureListe<T>, ajout: T): T[] | null {
  if (lecture.statut !== "pret") {
    return null;
  }
  return [...lecture.lignes, ajout];
}

export function listeSans<T>(lecture: LectureListe<T>, index: number): T[] | null {
  if (lecture.statut !== "pret" || index < 0 || index >= lecture.lignes.length) {
    return null;
  }
  return lecture.lignes.filter((_, i) => i !== index);
}
