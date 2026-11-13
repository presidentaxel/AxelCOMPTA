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
  versements_a_verifier?: number;
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
  const reconnecter = s.a_reconnecter > 0 ? `${base} · ${s.a_reconnecter} à reconnecter` : base;
  const n = s.versements_a_verifier ?? 0;
  return n > 0 ? `${reconnecter} · ${n} ${n > 1 ? "versements" : "versement"} à vérifier` : reconnecter;
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

/** AXE-891 : le motif technique d'un relevé « à vérifier », dit au chauffeur. */
const MOTIFS_EN_CLAIR: [string, string][] = [
  ["plusieurs virements possibles", "Plusieurs virements reçus peuvent correspondre."],
  ["virement déjà rapproché", "Le virement reçu correspond déjà à une autre période."],
  ["virement dans un exercice clos", "Le virement est arrivé sur un exercice déjà clôturé."],
  ["virement classé en ", "Le virement reçu n'est pas classé en recette."],
  ["relevé modifié après ventilation", "La plateforme a modifié ce relevé après coup."],
  ["ventilation annulée", "Le virement reçu a été reclassé après coup."],
  ["ventilation refusée", "Le versement n'a pas pu être enregistré."],
];

export function motifEnClair(motif: string | null): string {
  const trouve = MOTIFS_EN_CLAIR.find(([debut]) => (motif ?? "").startsWith(debut));
  return trouve ? trouve[1] : "Le relevé et le virement reçu ne concordent pas.";
}
