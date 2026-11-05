/** Lit un montant saisi en euros (« 1 000,50 », virgule, espaces y compris
 * insécables) et le rend en centimes. Une saisie vide ou illisible donne un
 * message : jamais zéro par défaut, jamais NaN. */
export type LectureMontant =
  | { centimes: number; message: null }
  | { centimes: null; message: string };

const MESSAGE_VIDE = "Indiquez un montant.";
const MESSAGE_ILLISIBLE = "Écrivez le montant comme 1 000,50.";

export function lireMontantEuros(saisie: string): LectureMontant {
  const compacte = saisie.trim().replace(/\s/gu, "");
  if (compacte === "") {
    return { centimes: null, message: MESSAGE_VIDE };
  }
  const normalise = compacte.replace(",", ".");
  const morceaux = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalise);
  // Au-delà, `Number` n'est plus exact au centime.
  if (morceaux?.[1] === undefined || morceaux[1].length > 12) {
    return { centimes: null, message: MESSAGE_ILLISIBLE };
  }
  const cents = (morceaux[2] ?? "").padEnd(2, "0");
  return { centimes: Number(morceaux[1]) * 100 + Number(cents), message: null };
}
