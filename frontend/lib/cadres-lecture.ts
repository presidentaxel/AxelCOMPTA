/** AXE-1015 : où chaque valeur lue par l'OCR se trouve dans le texte d'un
 * PDF, pour l'encadrer dans la préview. Pur : pdf.js fournit les morceaux de
 * texte et leur position, ici on ne fait que les comparer. */

export type MorceauTexte = { str: string; x: number; y: number; largeur: number; hauteur: number };
export type Cadre = { champ: string; x: number; y: number; largeur: number; hauteur: number };

type Montant = { nom: string; valeur_cts: number };

function normaliser(texte: string): string {
  return texte.toLowerCase().replace(/[\s  .,€]/g, "");
}

/** Un montant tel qu'il peut être imprimé : « 1 234,56 », « 1234.56 », « 1 234 »… */
export function formesMontant(cts: number): string[] {
  const euros = Math.abs(cts) / 100;
  const entier = Math.trunc(euros);
  const formes = [euros.toFixed(2)];
  if (cts % 100 === 0) formes.push(String(entier));
  return formes.map(normaliser);
}

/** Les valeurs à chercher : textes d'au moins 3 caractères, et montants non nuls. */
export function valeursAChercher(lu: Record<string, unknown>): { champ: string; formes: string[] }[] {
  const textes = Object.entries(lu)
    .filter(([, v]) => typeof v === "string" && normaliser(v).length >= 3)
    .map(([champ, v]) => ({ champ, formes: [normaliser(v as string)] }));
  const montants = (Array.isArray(lu.montants) ? (lu.montants as Montant[]) : [])
    .filter((m) => m.valeur_cts !== 0)
    .map((m) => ({ champ: m.nom, formes: formesMontant(m.valeur_cts) }));
  return [...textes, ...montants];
}

/** Les morceaux de texte qui contiennent une valeur lue.
 * shortcut: une valeur coupée sur deux morceaux de texte n'est pas trouvée ; les rassembler par ligne si ça manque souvent. */
export function trouverCadres(morceaux: MorceauTexte[], lu: Record<string, unknown>): Cadre[] {
  const valeurs = valeursAChercher(lu);
  const cadres: Cadre[] = [];
  for (const morceau of morceaux) {
    const texte = normaliser(morceau.str);
    if (!texte) continue;
    const trouvee = valeurs.find((v) => v.formes.some((f) => f && texte.includes(f)));
    if (trouvee) {
      cadres.push({ champ: trouvee.champ, x: morceau.x, y: morceau.y, largeur: morceau.largeur, hauteur: morceau.hauteur });
    }
  }
  return cadres;
}
