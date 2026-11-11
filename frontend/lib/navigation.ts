/** Entrées de la barre de navigation du gestionnaire (DESIGN.md § Navigation).
 * L'ordre est celui de la barre et du tiroir. */
export const ENTREES_GESTIONNAIRE = [
  { href: "/portefeuille", libelle: "Entreprises" },
  { href: "/expert", libelle: "Mode expert" },
  { href: "/connexions-bancaires", libelle: "Connexions bancaires" },
  { href: "/rappels", libelle: "Rappels" },
  { href: "/invitations", libelle: "Invitations" },
  { href: "/equipe", libelle: "Équipe" },
  { href: "/integrations", libelle: "Intégrations" },
] as const;

/** Une entrée est active sur sa page et sur toutes ses sous-pages
 * (`/expert/abc` allume « Mode expert »), mais pas sur une page dont le chemin
 * commence seulement par les mêmes lettres (`/equipes` n'allume pas
 * `/equipe`). */
export function entreeActive(chemin: string, href: string): boolean {
  return chemin === href || chemin.startsWith(`${href}/`);
}

/** Initiales de l'avatar : les deux premières lettres de l'e-mail, en
 * majuscules. « AX » tant que l'e-mail n'est pas connu. */
export function initiales(email: string): string {
  return email.slice(0, 2).toUpperCase() || "AX";
}
