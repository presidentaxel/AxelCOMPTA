// AXE-804 : reprise du bilan d'ouverture depuis le FEC de l'outil précédent.
// Ce que le serveur renvoie, et la lecture du formulaire. Pur, testé.

export type LigneOuverture = { compte: string; debit_cts: number; credit_cts: number };

export type AnalyseFec = {
  possible: boolean;
  siren: string;
  cloture: string;
  ouverture: string;
  nb_lignes: number;
  nb_ecritures: number;
  total_debit_cts: number;
  resultat_cts: number;
  solde_banque_cts: number;
  capital_cts: number;
  comptes_inconnus: string[];
  refus: string[];
  alertes: string[];
  attestation: string;
  a_nouveaux: LigneOuverture[];
};

export type OuvertureVue = {
  faite: boolean;
  nom_fichier?: string | null;
  cloture?: string | null;
  role?: string | null;
  auteur?: string | null;
  le?: string | null;
  deficits_euros?: number;
};

/** Seules les correspondances remplies partent au serveur, sans espaces. */
export function correspondanceJson(saisies: Record<string, string>): string {
  const remplies = Object.entries(saisies)
    .map(([source, cible]) => [source, cible.replace(/\s/gu, "")] as const)
    .filter(([, cible]) => cible !== "");
  return JSON.stringify(Object.fromEntries(remplies));
}

export type LectureDeficits = { euros: number; message: null } | { euros: null; message: string };

/** Déficits reportables en euros entiers (2033-D ligne 870). Vide : 0. */
export function lireDeficits(saisie: string): LectureDeficits {
  const propre = saisie.replace(/\s/gu, "");
  if (propre === "") return { euros: 0, message: null };
  if (!/^\d{1,12}$/u.test(propre)) {
    return { euros: null, message: "Indiquez les déficits en euros entiers, sans centimes." };
  }
  return { euros: Number(propre), message: null };
}

/** Qui a repris le bilan, en une phrase. */
export function phraseOuverture(ouverture: OuvertureVue): string | null {
  if (!ouverture.faite) return null;
  const qui =
    ouverture.role === "expert_comptable" ? `l'expert-comptable ${ouverture.auteur ?? ""}`.trim() : "le dirigeant";
  const fichier = ouverture.nom_fichier ? ` (${ouverture.nom_fichier})` : "";
  return `Bilan d'ouverture repris par ${qui}${fichier}.`;
}
