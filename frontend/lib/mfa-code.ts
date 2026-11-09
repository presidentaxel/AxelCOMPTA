/** Adresse réservée à la double authentification, hors de l'application. */
export const CHEMIN_DOUBLE_AUTHENTIFICATION = "/double-authentification";

/** Ce qui se décide sans réseau dans la double authentification (AXE-812). */

export type Facteur = { id: string; factor_type: string; status: string };

export const LONGUEUR_CODE = 6;

/** Six chiffres, espaces tolérés (« 123 456 » recopié d'une application). */
export function codeNormalise(saisie: string): string | null {
  const code = saisie.replace(/\s+/g, "");
  return /^\d{6}$/.test(code) ? code : null;
}

/** Le facteur TOTP déjà vérifié, s'il y en a un. */
export function facteurVerifie(facteurs: readonly Facteur[]): Facteur | null {
  return facteurs.find((f) => f.factor_type === "totp" && f.status === "verified") ?? null;
}

/** Écrit les chiffres tapés ou collés à partir de `index`, et dit quelle
 * case prendre ensuite : la suivante, ou la dernière si le code est plein. */
export function ecrireChiffres(
  cases: readonly string[],
  index: number,
  brut: string,
): { cases: string[]; focus: number } {
  const chiffres = brut.replace(/\D/g, "").slice(0, LONGUEUR_CODE - index);
  if (!chiffres) return { cases: [...cases], focus: index };
  const suivantes = [...cases];
  for (let i = 0; i < chiffres.length; i++) suivantes[index + i] = chiffres[i] ?? "";
  return { cases: suivantes, focus: Math.min(index + chiffres.length, LONGUEUR_CODE - 1) };
}

/** Efface la case courante. Si elle est déjà vide, efface la précédente
 * et y revient : un chiffre de trop se corrige dans le même geste. */
export function effacerChiffre(
  cases: readonly string[],
  index: number,
): { cases: string[]; focus: number } {
  const suivantes = [...cases];
  if (suivantes[index]) {
    suivantes[index] = "";
    return { cases: suivantes, focus: index };
  }
  if (index === 0) return { cases: suivantes, focus: 0 };
  suivantes[index - 1] = "";
  return { cases: suivantes, focus: index - 1 };
}

/** Supabase renvoie le QR en SVG brut. Un `<img src>` ne l'affiche pas
 * (le « # » des couleurs coupe l'adresse) : on le réencode en image. */
export function imageDuQr(qr: string): string {
  const texte = qr.trim();
  if (texte.startsWith("data:image/")) return texte;
  const debut = texte.indexOf("<svg");
  if (debut < 0) return texte;
  const octets = new TextEncoder().encode(texte.slice(debut));
  let binaire = "";
  for (const octet of octets) binaire += String.fromCharCode(octet);
  return `data:image/svg+xml;base64,${btoa(binaire)}`;
}
