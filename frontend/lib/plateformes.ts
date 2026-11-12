/** Mêmes formes que `PlateformeReliee` (auth-chauffeur) et
 * `SynthesePlateformes` (auth-gestionnaire), sans les importer : ce fichier
 * est compilé seul pour les tests unitaires. */
type PlateformeReliee = {
  nom: string;
  etat: "connecte" | "en_cours" | "a_reconnecter";
  relie_le: string | null;
};
type SynthesePlateformes = {
  reliees: number;
  attendues: number;
  a_reconnecter: number;
  manquantes: string[];
};

/** AXE-819 : « Uber : relié le 06/11 », « Bolt : à reconnecter ». */
export function etatPlateforme(compte: PlateformeReliee, formatDate: (iso: string) => string): string {
  if (compte.etat === "connecte") {
    return compte.relie_le ? `relié le ${formatDate(compte.relie_le.slice(0, 10))}` : "relié";
  }
  return compte.etat === "en_cours" ? "reconnexion en cours" : "à reconnecter";
}

/** Côté gestionnaire : « Plateformes reliées : 1/2 · 1 à reconnecter ». */
export function resumePlateformes(s: SynthesePlateformes): string {
  const base =
    s.attendues > 0
      ? `Plateformes reliées : ${Math.min(s.reliees, s.attendues)}/${s.attendues}`
      : s.reliees > 0
        ? `Plateformes reliées : ${s.reliees}`
        : "Aucune plateforme reliée";
  return s.a_reconnecter > 0 ? `${base} · ${s.a_reconnecter} à reconnecter` : base;
}

/** AXE-821 : où en est le rapprochement d'un versement avec la banque. */
export const ETATS_VERSEMENT: Record<string, string> = {
  en_attente_banque: "virement pas encore reçu",
  reconcilie: "rapproché",
  a_classer: "à classer en recette",
  a_verifier: "à vérifier",
};

export function etatVersement(etat: string, motif: string | null): string {
  const libelle = ETATS_VERSEMENT[etat] ?? etat;
  return etat === "a_verifier" && motif ? `${libelle} : ${motif}` : libelle;
}
