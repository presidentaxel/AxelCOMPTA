/** AXE-911 : le lien entre un chauffeur et son compte Rollee, côté
 * gestionnaire. Des initiales, des plateformes, une fin d'IBAN : jamais un
 * montant ni un nom en clair (doc 19). Compilé seul pour les tests. */

export type EtatRollee =
  | "relie_auto"
  | "relie_gestionnaire"
  | "relie_chauffeur"
  | "a_choisir"
  | "non_relie";

export type CandidatRollee = { dossier_id: string; nom: string; raisons: string[] };

export type AChoisirRollee = {
  rollee_user_id: string;
  etat: "a_choisir" | "non_trouve";
  initiales: string;
  plateformes: string[];
  iban_fin: string | null;
  candidats: CandidatRollee[];
};

export type RolleePortefeuille = {
  etats: Record<string, EtatRollee>;
  a_choisir: AChoisirRollee[];
};

export type LienRollee = { origine: string; comment: string; relie_le: string };
export type LienRetire = {
  comment: string;
  relie_le: string;
  retire_le: string;
  retire_par: string;
  motif: string;
};
export type FicheRollee = {
  lien: LienRollee | null;
  historique: LienRetire[];
  versements_a_contrepasser: number;
};

export const LIBELLES_ETAT_ROLLEE: Record<EtatRollee, string> = {
  relie_auto: "relié automatiquement",
  relie_gestionnaire: "relié par le gestionnaire",
  relie_chauffeur: "relié par le chauffeur",
  a_choisir: "à choisir",
  non_relie: "non trouvé",
};

/** « K.B. · Uber, Bolt · IBAN …0189 » : de quoi reconnaître sans identifier. */
export function apercuCompte(compte: AChoisirRollee): string {
  const morceaux = [
    compte.initiales || "Sans nom",
    compte.plateformes.join(", ") || "aucune plateforme",
  ];
  if (compte.iban_fin) morceaux.push(`IBAN …${compte.iban_fin}`);
  return morceaux.join(" · ");
}

/** Les comptes Rollee à relier depuis la fiche de cette entreprise. */
export function comptesPourLaFiche(vue: RolleePortefeuille, dossierId: string): AChoisirRollee[] {
  return vue.a_choisir.filter(
    (compte) =>
      compte.etat === "a_choisir" &&
      compte.candidats.some((candidat) => candidat.dossier_id === dossierId),
  );
}

/** Le bandeau au-dessus de la liste, ou `null` s'il n'y a rien à choisir. */
export function bandeauRollee(vue: RolleePortefeuille): string | null {
  const a = vue.a_choisir.filter((c) => c.etat === "a_choisir").length;
  const n = vue.a_choisir.filter((c) => c.etat === "non_trouve").length;
  if (a + n === 0) return null;
  const parties = [];
  if (a > 0) parties.push(a === 1 ? "1 compte Rollee attend votre choix" : `${a} comptes Rollee attendent votre choix`);
  if (n > 0) parties.push(n === 1 ? "1 n'a été rapproché d'aucune entreprise" : `${n} n'ont été rapprochés d'aucune entreprise`);
  return `${parties.join(", ")}. Sans ce lien, les revenus Uber et Bolt n'arrivent pas.`;
}

/** Ce que retirer le lien change, dit avant de confirmer. */
export function effetDelier(versements: number): string {
  if (versements === 0) return "Aucun versement n'a encore été importé par ce lien.";
  const qui = versements === 1 ? "Le versement déjà importé sera contre-passé" : `Les ${versements} versements déjà importés seront contre-passés`;
  return `${qui}, jamais supprimé. Une période close n'est pas touchée : l'écart passe sur l'exercice ouvert.`;
}
