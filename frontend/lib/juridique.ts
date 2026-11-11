// AXE-859 : les textes juridiques vivent en Markdown dans `docs/juridique/`
// (versionnés, relus par un juriste avec AXE-813). Ce module en lit le
// sous-ensemble utilisé (titres, paragraphes, listes, citations, tableaux,
// gras, liens entre textes) en blocs simples à afficher. Pur, testé.

export const TEXTES_JURIDIQUES = {
  "mentions-legales": "Mentions légales",
  "cgu-chauffeur": "Conditions d'utilisation",
  "cgv-gestionnaire": "Conditions générales (gestionnaire)",
  confidentialite: "Confidentialité",
  "engagement-expert-comptable": "Engagement de l'expert-comptable",
} as const;

export type CleTexte = keyof typeof TEXTES_JURIDIQUES;

export function estCleTexte(cle: string): cle is CleTexte {
  return Object.hasOwn(TEXTES_JURIDIQUES, cle);
}

/** Morceau de texte : simple, en gras, ou lien vers un autre texte. */
export type Morceau =
  | { type: "texte"; texte: string }
  | { type: "gras"; texte: string }
  | { type: "lien"; texte: string; cle: CleTexte };

export type Bloc =
  | { type: "titre"; niveau: 1 | 2 | 3; morceaux: Morceau[] }
  | { type: "paragraphe"; morceaux: Morceau[] }
  | { type: "liste"; ordonnee: boolean; elements: Morceau[][] }
  | { type: "encadre"; morceaux: Morceau[] }
  | { type: "tableau"; entete: Morceau[][]; lignes: Morceau[][][] };

/** `**gras**`, `[texte](cle.md)` vers un autre texte ; un lien vers autre
 * chose garde son texte, sans lien. Les accents graves sont retirés. */
export function lireMorceaux(ligne: string): Morceau[] {
  const morceaux: Morceau[] = [];
  const motif = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/gu;
  let reste = 0;
  for (const trouve of ligne.matchAll(motif)) {
    const debut = trouve.index ?? 0;
    if (debut > reste) morceaux.push({ type: "texte", texte: nettoyer(ligne.slice(reste, debut)) });
    if (trouve[1] !== undefined) {
      morceaux.push({ type: "gras", texte: nettoyer(trouve[1]) });
    } else {
      const cle = (trouve[3] ?? "").replace(/\.md$/u, "");
      const texte = nettoyer(trouve[2] ?? "");
      morceaux.push(estCleTexte(cle) ? { type: "lien", texte, cle } : { type: "texte", texte });
    }
    reste = debut + trouve[0].length;
  }
  if (reste < ligne.length) morceaux.push({ type: "texte", texte: nettoyer(ligne.slice(reste)) });
  return morceaux;
}

function nettoyer(texte: string): string {
  return texte.replace(/`/gu, "");
}

function cellules(ligne: string): string[] {
  return ligne.trim().replace(/^\|/u, "").replace(/\|$/u, "").split("|").map((c) => c.trim());
}

/** Les blocs d'un texte. Une ligne vide sépare deux paragraphes ; une ligne
 * qui continue une liste ou une citation s'ajoute à son dernier élément. */
export function lireTexte(markdown: string): Bloc[] {
  const blocs: Bloc[] = [];
  let courant: string[] = [];
  let mode: "paragraphe" | "encadre" | null = null;

  function fermer() {
    if (courant.length > 0 && mode) {
      blocs.push({ type: mode, morceaux: lireMorceaux(courant.join(" ")) });
    }
    courant = [];
    mode = null;
  }

  const lignes = markdown.split("\n");
  for (let i = 0; i < lignes.length; i += 1) {
    const ligne = lignes[i] ?? "";
    const titre = /^(#{1,3})\s+(.*)$/u.exec(ligne);
    const element = /^(\s*)(-|\d+\.)\s+(.*)$/u.exec(ligne);
    if (ligne.trim() === "") {
      fermer();
    } else if (titre) {
      fermer();
      blocs.push({ type: "titre", niveau: (titre[1]?.length ?? 1) as 1 | 2 | 3, morceaux: lireMorceaux(titre[2] ?? "") });
    } else if (ligne.startsWith("|")) {
      fermer();
      const tableau: string[] = [];
      while (i < lignes.length && (lignes[i] ?? "").startsWith("|")) tableau.push(lignes[i++] ?? "");
      i -= 1;
      const [entete = "", , ...corps] = tableau;
      blocs.push({
        type: "tableau",
        entete: cellules(entete).map(lireMorceaux),
        lignes: corps.map((l) => cellules(l).map(lireMorceaux)),
      });
    } else if (element) {
      fermer();
      const ordonnee = /\d/u.test(element[2] ?? "");
      const precedent = blocs.at(-1);
      const elements = precedent?.type === "liste" && precedent.ordonnee === ordonnee ? precedent.elements : [];
      const texte = [element[3] ?? ""];
      while (i + 1 < lignes.length && /^\s{2,}\S/u.test(lignes[i + 1] ?? "")) texte.push((lignes[++i] ?? "").trim());
      elements.push(lireMorceaux(texte.join(" ")));
      if (elements.length === 1) blocs.push({ type: "liste", ordonnee, elements });
    } else if (ligne.startsWith(">")) {
      if (mode !== "encadre") fermer();
      mode = "encadre";
      courant.push(ligne.replace(/^>\s?/u, ""));
    } else {
      if (mode !== "paragraphe") fermer();
      mode = "paragraphe";
      courant.push(ligne.trim());
    }
  }
  fermer();
  return blocs;
}
