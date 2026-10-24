import type { DossierAgregat } from "@/lib/types";

/** Même ordre que la frise du portefeuille. */
export const ETAPES_FRISE = [
  "Compte",
  "Clôture",
  "Signature",
  "Greffe",
  "Impôts",
  "Signature légale",
] as const;

export type EtapeFrise = (typeof ETAPES_FRISE)[number];

/** Dernière étape atteinte. « Suivi » et un compte ouvert valent « Compte ».
 * « Compte » sans compte ouvert vaut -1 : le point n'est pas encore coché. */
export function rangEtape(etape: string, compteOuvert: boolean): number {
  if (etape === "Suivi" || (etape === "Compte" && compteOuvert)) {
    return ETAPES_FRISE.indexOf("Compte");
  }
  if (etape === "Signé") return ETAPES_FRISE.indexOf("Greffe");
  const index = ETAPES_FRISE.indexOf(etape as EtapeFrise);
  return etape === "Compte" ? -1 : index;
}

/** L'année en est à cette étape, ou ne l'a pas encore passée.
 * « Sans exercice » ne compte pas : il n'y a pas de frise à filtrer. */
export function etapePasEncorePassee(
  etape: string,
  compteOuvert: boolean,
  cible: string,
): boolean {
  if (etape === "Sans exercice") return false;
  const cibleRang = ETAPES_FRISE.indexOf(cible as EtapeFrise);
  if (cibleRang < 0) return false;
  const rang = rangEtape(etape, compteOuvert);
  if (rang < 0) return true;
  return rang <= cibleRang;
}

/** Le dépôt aux impôts n'est pas le dernier jalon atteint, ni un jalon ultérieur. */
export function impotsNonDeclares(etape: string, compteOuvert: boolean): boolean {
  if (etape === "Sans exercice") return false;
  const rang = rangEtape(etape, compteOuvert);
  if (rang < 0) return true;
  return rang < ETAPES_FRISE.indexOf("Impôts");
}

export function gardeEtape(dossier: DossierAgregat, cible: string): boolean {
  const ouvert = dossier.statut_invitation === "actif";
  return (
    etapePasEncorePassee(dossier.etape_courante, ouvert, cible) ||
    etapePasEncorePassee(dossier.etape_precedente, ouvert, cible)
  );
}

export function nonDeclarePourAnnee(dossier: DossierAgregat, annee: number): boolean {
  const ouvert = dossier.statut_invitation === "actif";
  if (dossier.annee_courante === annee && impotsNonDeclares(dossier.etape_courante, ouvert)) {
    return true;
  }
  return (
    dossier.annee_precedente === annee && impotsNonDeclares(dossier.etape_precedente, ouvert)
  );
}
