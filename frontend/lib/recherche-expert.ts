/** Recherche de la file expert (AXE-925) : chaque mot doit se retrouver
 * dans le libellé, l'entreprise, le compte ou le montant. */

export type LigneCherchable = {
  libelle: string;
  dossier_nom: string;
  montant_cts: number | null;
  detail?: string;
  compte_actuel?: string | null;
  compte_suggere?: string | null;
  compte?: string;
};

const MONTANT = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function sansAccent(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function texteDe(ligne: LigneCherchable): string {
  const euros = ligne.montant_cts === null ? "" : MONTANT.format(Math.abs(ligne.montant_cts) / 100);
  return sansAccent(
    [
      ligne.libelle,
      ligne.dossier_nom,
      ligne.detail ?? "",
      ligne.compte_actuel ?? "",
      ligne.compte_suggere ?? "",
      ligne.compte ?? "",
      euros,
    ].join(" "),
  );
}

export function chercheExpert<T extends LigneCherchable>(lignes: T[], saisie: string): T[] {
  const jetons = sansAccent(saisie).split(/\s+/).filter(Boolean);
  if (jetons.length === 0) return lignes;
  return lignes.filter((ligne) => {
    const texte = texteDe(ligne);
    return jetons.every((jeton) => texte.includes(jeton));
  });
}
